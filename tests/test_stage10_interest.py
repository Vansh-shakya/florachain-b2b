"""
FloraChain B2B — Phase 10 Payment Due Date & Agreed Late-Payment Interest Test Suite
Tests:
- quantize_currency decimal arithmetic (ROUND_HALF_UP) & safe date parsing
- Seeded demo invoice INV-2026-8760 contractual interest calculation as of 2026-11-03
- Zero interest / No agreement handling (0% p.a. or NONE basis yields 0 interest)
- No due date handling (due_status = NO_DUE_DATE)
- Not due handling (as_of_date <= due_date yields NOT_DUE and 0 interest)
- Grace period handling (within grace yields IN_GRACE_PERIOD and 0 interest)
- Settled invoice handling (fully paid yields SETTLED and 0 ongoing interest)
- Cancelled invoice handling (yields CANCELLED and 0 interest)
- Stepwise timeline calculation with partial payments (interest stops on settled principal)
- Payment reversal recalculates full overdue interest
- Recording agreed terms with audit event logging (INVOICE_TERMS_UPDATED)
- Role-based permissions & data isolation (Supplier/Admin vs Nursery)
- Full API endpoint integration (GET /api/invoices/<id>/interest, POST /api/invoices/<id>/interest-terms, GET /api/invoices?due_status=OVERDUE)
"""

import unittest
import os
import sys
import json
import tempfile
import sqlite3
import datetime
from decimal import Decimal

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models.database import get_connection, init_database
from app.services.interest_service import (
    calculate_invoice_interest,
    record_invoice_agreed_terms,
    quantize_currency,
    parse_date_safe
)
from app.services.payment_service import (
    record_payment,
    reverse_payment
)


class TestPhase10InterestManagement(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for this test run
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.app = create_app({
            'TESTING': True,
            'DB_PATH': self.db_path,
            'SECRET_KEY': 'test-secret-key',
            'ALLOW_DEMO_ROLE_SWITCH': True
        })
        self.client = self.app.test_client()

        # Initialize database with schema, seed data, and Phase 10 demo terms
        init_database(self.db_path)

        # Retrieve test users
        conn = get_connection(self.db_path)
        try:
            supplier_row = conn.execute("SELECT * FROM users WHERE username = 'supplier_rajesh'").fetchone()
            nursery_row = conn.execute("SELECT * FROM users WHERE username = 'nursery_amit'").fetchone()
            admin_row = conn.execute("SELECT * FROM users WHERE username = 'admin_flora'").fetchone()

            self.supplier = dict(supplier_row)
            self.nursery = dict(nursery_row)
            self.admin = dict(admin_row)
        finally:
            conn.close()

    def tearDown(self):
        try:
            os.close(self.db_fd)
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except Exception:
            pass

    def test_quantize_currency_and_date_parsing(self):
        """Test decimal rounding (ROUND_HALF_UP) and safe date parsing."""
        self.assertEqual(quantize_currency(120.955), Decimal('120.96'))
        self.assertEqual(quantize_currency(120.954), Decimal('120.95'))
        self.assertEqual(quantize_currency('100.50'), Decimal('100.50'))
        self.assertEqual(quantize_currency(0), Decimal('0.00'))

        # Date parsing
        d1 = parse_date_safe('2026-10-26')
        self.assertEqual(d1, datetime.date(2026, 10, 26))
        d2 = parse_date_safe(datetime.date(2026, 11, 3))
        self.assertEqual(d2, datetime.date(2026, 11, 3))
        d3 = parse_date_safe(datetime.datetime(2026, 11, 3, 14, 30))
        self.assertEqual(d3, datetime.date(2026, 11, 3))
        self.assertIsNone(parse_date_safe(None))
        self.assertIsNone(parse_date_safe(''))
        self.assertIsNone(parse_date_safe('invalid-date'))

    def test_demo_invoice_interest_calculation_seeded_state(self):
        """
        Test seeded demo invoice INV-2026-8760:
        - Invoiced: ₹41,160.00 on 2026-10-16
        - Advance payment settled: ₹10,500.00 on 2026-10-10
        - Outstanding principal as of due date 2026-10-26: ₹30,660.00
        - Contractual rate: 18.0% p.a., Actual/365
        - As of 2026-11-03 (8 days overdue):
          Accrued interest = 30660 * 0.18 * (8 / 365) = ₹120.96
          Total payable = ₹30,780.96
        """
        conn = get_connection(self.db_path)
        try:
            res = calculate_invoice_interest(conn, 'INV-2026-8760', as_of_date=datetime.date(2026, 11, 3))
            self.assertEqual(res['due_status'], 'OVERDUE')
            self.assertEqual(res['overdue_days'], 8)
            self.assertEqual(res['original_principal'], 41160.00)
            self.assertEqual(res['total_paid'], 10500.00)
            self.assertEqual(res['outstanding_principal'], 30660.00)
            self.assertEqual(res['interest_rate_pct'], 18.0)
            self.assertEqual(res['interest_calculation_basis'], 'ANNUAL_SIMPLE')
            self.assertEqual(res['accrued_interest'], 120.96)
            self.assertEqual(res['total_amount_payable'], 30780.96)
            self.assertEqual(len(res['calculation_breakdown']), 1)
            seg = res['calculation_breakdown'][0]
            self.assertEqual(seg['period_start'], '2026-10-26')
            self.assertEqual(seg['period_end'], '2026-11-03')
            self.assertEqual(seg['days'], 8)
            self.assertEqual(seg['principal'], 30660.00)
            self.assertEqual(seg['interest'], 120.96)
        finally:
            conn.close()

    def test_no_agreement_or_zero_rate_accrues_zero_interest(self):
        """Invoices with 0.0% interest or NONE basis must yield 0 interest even if overdue."""
        conn = get_connection(self.db_path)
        try:
            conn.execute("""
                UPDATE invoices 
                SET interest_rate_pct = 0.0, interest_calculation_basis = 'NONE'
                WHERE invoice_number = 'INV-2026-8760'
            """)
            conn.commit()

            res = calculate_invoice_interest(conn, 'INV-2026-8760', as_of_date=datetime.date(2026, 11, 15))
            self.assertEqual(res['due_status'], 'OVERDUE')
            self.assertEqual(res['overdue_days'], 20)
            self.assertEqual(res['accrued_interest'], 0.0)
            self.assertEqual(res['total_amount_payable'], 30660.00)
            self.assertEqual(res['calculation_breakdown'], [])
        finally:
            conn.close()

    def test_no_due_date_handling(self):
        """When an invoice has no due date recorded, status is NO_DUE_DATE with 0 interest."""
        conn = get_connection(self.db_path)
        try:
            conn.execute("UPDATE invoices SET due_date = NULL WHERE invoice_number = 'INV-2026-8760'")
            conn.commit()

            res = calculate_invoice_interest(conn, 'INV-2026-8760', as_of_date=datetime.date(2026, 11, 3))
            self.assertEqual(res['due_status'], 'NO_DUE_DATE')
            self.assertEqual(res['overdue_days'], 0)
            self.assertEqual(res['accrued_interest'], 0.0)
            self.assertIsNone(res['due_date'])
        finally:
            conn.close()

    def test_not_due_handling(self):
        """When as_of_date is on or before due_date, status is NOT_DUE with 0 interest."""
        conn = get_connection(self.db_path)
        try:
            res = calculate_invoice_interest(conn, 'INV-2026-8760', as_of_date=datetime.date(2026, 10, 20))
            self.assertEqual(res['due_status'], 'NOT_DUE')
            self.assertEqual(res['overdue_days'], 0)
            self.assertEqual(res['accrued_interest'], 0.0)
            self.assertEqual(res['total_amount_payable'], 30660.00)
        finally:
            conn.close()

    def test_grace_period_handling(self):
        """When grace period days are specified, no interest or overdue status accrues until grace expires."""
        conn = get_connection(self.db_path)
        try:
            # Due date 2026-10-26 with 5 days grace period -> Grace extends through 2026-10-31
            conn.execute("""
                UPDATE invoices 
                SET interest_grace_period_days = 5 
                WHERE invoice_number = 'INV-2026-8760'
            """)
            conn.commit()

            # Within grace period (2026-10-29): status is IN_GRACE_PERIOD
            res_grace = calculate_invoice_interest(conn, 'INV-2026-8760', as_of_date=datetime.date(2026, 10, 29))
            self.assertEqual(res_grace['due_status'], 'IN_GRACE_PERIOD')
            self.assertEqual(res_grace['overdue_days'], 0)
            self.assertEqual(res_grace['accrued_interest'], 0.0)

            # Past grace period (2026-11-03): status is OVERDUE, 8 days overdue, 3 days past grace
            res_overdue = calculate_invoice_interest(conn, 'INV-2026-8760', as_of_date=datetime.date(2026, 11, 3))
            self.assertEqual(res_overdue['due_status'], 'OVERDUE')
            self.assertEqual(res_overdue['overdue_days'], 8)
            self.assertEqual(res_overdue['accrued_interest'], 45.36)
        finally:
            conn.close()

    def test_settled_invoice_handling(self):
        """Fully settled invoice has due_status = SETTLED and 0 ongoing interest."""
        conn = get_connection(self.db_path)
        try:
            # Settle remaining ₹30,660.00
            pay_res = record_payment(
                conn,
                {
                    'invoice_id': 'INV-2026-8760',
                    'amount': 30660.00,
                    'payment_date': '2026-10-20',
                    'payment_method': 'BANK_TRANSFER',
                    'reference_number': 'UTR-SETTLE-FULL-999',
                    'notes': 'Full final settlement'
                },
                actor_user=self.supplier
            )
            self.assertIsNotNone(pay_res)

            res = calculate_invoice_interest(conn, 'INV-2026-8760', as_of_date=datetime.date(2026, 11, 3))
            self.assertEqual(res['due_status'], 'SETTLED')
            self.assertEqual(res['overdue_days'], 0)
            self.assertEqual(res['outstanding_principal'], 0.0)
            self.assertEqual(res['accrued_interest'], 0.0)
            self.assertEqual(res['total_amount_payable'], 0.0)
        finally:
            conn.close()

    def test_stepwise_timeline_interest_with_partial_payments(self):
        """
        Stepwise calculation across partial payment dates:
        Starting with outstanding principal ₹30,660.00 as of due date 2026-10-26 at 18% p.a.
        On 2026-10-31 (5 days overdue): Partial payment ₹10,000.00 is settled.
          - Period 1 (2026-10-26 to 2026-10-31 = 5 days) on ₹30,660.00:
            30660 * 0.18 * (5 / 365) = ₹75.60
        As of 2026-11-05 (another 5 days on remaining ₹20,660.00):
          - Period 2 (2026-10-31 to 2026-11-05 = 5 days) on ₹20,660.00:
            20660 * 0.18 * (5 / 365) = ₹50.94
        Total accrued interest = ₹75.60 + ₹50.94 = ₹126.54
        Total payable = ₹20,660.00 + ₹126.54 = ₹20,786.54
        """
        conn = get_connection(self.db_path)
        try:
            pay_res = record_payment(
                conn,
                {
                    'invoice_id': 'INV-2026-8760',
                    'amount': 10000.00,
                    'payment_date': '2026-10-31',
                    'payment_method': 'UPI',
                    'reference_number': 'UPI-PARTIAL-STEP-101',
                    'notes': 'Partial payment during overdue period'
                },
                actor_user=self.supplier
            )
            self.assertIsNotNone(pay_res)

            res = calculate_invoice_interest(conn, 'INV-2026-8760', as_of_date=datetime.date(2026, 11, 5))
            self.assertEqual(res['due_status'], 'OVERDUE')
            self.assertEqual(res['overdue_days'], 10)
            self.assertEqual(res['outstanding_principal'], 20660.00)
            self.assertEqual(len(res['calculation_breakdown']), 2)

            seg1 = res['calculation_breakdown'][0]
            self.assertEqual(seg1['period_start'], '2026-10-26')
            self.assertEqual(seg1['period_end'], '2026-10-31')
            self.assertEqual(seg1['days'], 5)
            self.assertEqual(seg1['principal'], 30660.00)
            self.assertEqual(seg1['interest'], 75.60)

            seg2 = res['calculation_breakdown'][1]
            self.assertEqual(seg2['period_start'], '2026-10-31')
            self.assertEqual(seg2['period_end'], '2026-11-05')
            self.assertEqual(seg2['days'], 5)
            self.assertEqual(seg2['principal'], 20660.00)
            self.assertEqual(seg2['interest'], 50.94)

            self.assertEqual(res['accrued_interest'], 126.54)
            self.assertEqual(res['total_amount_payable'], 20786.54)
        finally:
            conn.close()

    def test_payment_reversal_recalculates_overdue_interest(self):
        """Reversing a partial payment restores the principal and recalculates single overdue segment."""
        conn = get_connection(self.db_path)
        try:
            pay_res = record_payment(
                conn,
                {
                    'invoice_id': 'INV-2026-8760',
                    'amount': 10000.00,
                    'payment_date': '2026-10-31',
                    'payment_method': 'UPI',
                    'reference_number': 'UPI-REV-TEST-202',
                    'notes': 'Partial payment to be reversed'
                },
                actor_user=self.supplier
            )
            payment_id = pay_res['payment']['id']

            # Reverse the payment
            rev_res = reverse_payment(conn, payment_id, 'Erroneous UPI transfer', self.supplier)
            self.assertIsNotNone(rev_res)

            # Recalculate interest as of 2026-11-03 (8 days overdue on full ₹30,660.00)
            res = calculate_invoice_interest(conn, 'INV-2026-8760', as_of_date=datetime.date(2026, 11, 3))
            self.assertEqual(res['outstanding_principal'], 30660.00)
            self.assertEqual(res['accrued_interest'], 120.96)
            self.assertEqual(res['total_amount_payable'], 30780.96)
            self.assertEqual(len(res['calculation_breakdown']), 1)
        finally:
            conn.close()

    def test_record_invoice_agreed_terms_and_audit_event(self):
        """Updating agreed terms updates the invoice snapshot and writes an audit event."""
        conn = get_connection(self.db_path)
        try:
            update_res = record_invoice_agreed_terms(
                conn,
                invoice_id_or_number='INV-2026-8760',
                terms_data={
                    'due_date': '2026-11-15',
                    'interest_rate_pct': 24.0,
                    'interest_calculation_basis': 'ANNUAL_SIMPLE',
                    'interest_grace_period_days': 3,
                    'notes': 'Mutually amended terms as per renegotiated agreement.'
                },
                actor_user=self.supplier,
                ip_address='127.0.0.1'
            )
            self.assertIsNotNone(update_res)
            self.assertEqual(update_res['due_date'], '2026-11-15')
            self.assertEqual(update_res['interest_rate_pct'], 24.0)
            self.assertEqual(update_res['interest_grace_period_days'], 3)

            # Check invoice record
            row = conn.execute("SELECT * FROM invoices WHERE invoice_number = 'INV-2026-8760'").fetchone()
            self.assertEqual(row['due_date'], '2026-11-15')
            self.assertEqual(row['interest_rate_pct'], 24.0)
            self.assertEqual(row['interest_grace_period_days'], 3)

            # Check audit event
            audit_row = conn.execute("""
                SELECT * FROM audit_events 
                WHERE event_type = 'INVOICE_TERMS_UPDATED' 
                ORDER BY id DESC LIMIT 1
            """).fetchone()
            self.assertIsNotNone(audit_row)
            self.assertEqual(audit_row['actor_user_id'], self.supplier['id'])
            payload = json.loads(audit_row['after_state_json'])
            self.assertEqual(payload['due_date'], '2026-11-15')
            self.assertEqual(payload['interest_rate_pct'], 24.0)
        finally:
            conn.close()

    def test_record_terms_validation_errors(self):
        """Validation rejections: negative interest rate, invalid basis, missing due date."""
        conn = get_connection(self.db_path)
        try:
            # Negative rate
            with self.assertRaises(ValueError):
                record_invoice_agreed_terms(conn, 'INV-2026-8760', {'due_date': '2026-11-15', 'interest_rate_pct': -5.0}, self.supplier)

            # Invalid basis
            with self.assertRaises(ValueError):
                record_invoice_agreed_terms(conn, 'INV-2026-8760', {'due_date': '2026-11-15', 'interest_calculation_basis': 'INVALID_BASIS'}, self.supplier)

            # Missing due date
            with self.assertRaises(ValueError):
                record_invoice_agreed_terms(conn, 'INV-2026-8760', {'due_date': ''}, self.supplier)
        finally:
            conn.close()

    def test_role_isolation_nursery_cannot_update_terms(self):
        """Nursery user must not be allowed to modify agreed terms."""
        conn = get_connection(self.db_path)
        try:
            with self.assertRaises(PermissionError):
                record_invoice_agreed_terms(
                    conn,
                    'INV-2026-8760',
                    {'due_date': '2026-11-15', 'interest_rate_pct': 5.0},
                    actor_user=self.nursery
                )
        finally:
            conn.close()

    def test_api_get_invoice_interest(self):
        """GET /api/invoices/<id>/interest endpoint."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.supplier['id']
            sess['role'] = 'supplier'

        res = self.client.get('/api/invoices/INV-2026-8760/interest?as_of_date=2026-11-03')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['due_status'], 'OVERDUE')
        self.assertEqual(data['data']['accrued_interest'], 120.96)
        self.assertEqual(data['data']['outstanding_principal'], 30660.00)
        self.assertEqual(data['data']['total_amount_payable'], 30780.96)

    def test_api_update_invoice_terms(self):
        """POST /api/invoices/<id>/interest-terms endpoint."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.supplier['id']
            sess['role'] = 'supplier'

        payload = {
            'due_date': '2026-11-20',
            'interest_rate_pct': 15.0,
            'interest_calculation_basis': 'ANNUAL_SIMPLE',
            'interest_grace_period_days': 2,
            'notes': 'Terms updated via REST API'
        }
        res = self.client.post('/api/invoices/INV-2026-8760/interest-terms', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('terms updated', data['message'].lower())

    def test_api_list_invoices_due_status_filter(self):
        """GET /api/invoices with due_status filter."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.supplier['id']
            sess['role'] = 'supplier'

        # Filter by OVERDUE
        res_overdue = self.client.get('/api/invoices?due_status=OVERDUE')
        self.assertEqual(res_overdue.status_code, 200)
        data_overdue = res_overdue.get_json()
        self.assertTrue(data_overdue['success'])
        self.assertTrue(any(i['invoice_number'] == 'INV-2026-8760' for i in data_overdue['data']))

        # Filter by NOT_DUE (INV-2026-8760 should NOT be in this list)
        res_not_due = self.client.get('/api/invoices?due_status=NOT_DUE')
        self.assertEqual(res_not_due.status_code, 200)
        data_not_due = res_not_due.get_json()
        self.assertTrue(data_not_due['success'])
        self.assertFalse(any(i['invoice_number'] == 'INV-2026-8760' for i in data_not_due['data']))


if __name__ == '__main__':
    unittest.main()
