"""
FloraChain B2B — Phase 9 Payment Management & Settlement Test Suite
Tests:
- Initial demo payment retrieval & balance verification
- Recording multiple partial payments against an issued invoice
- Outstanding balance reduction & PAID status transition
- Overpayment prevention (rejecting payment > outstanding balance)
- Duplicate transaction/reference number rejection
- Zero and negative amount rejection
- Decimal/paise precision without floating-point errors
- Advance payment recording & unallocated balance tracking
- Advance allocation to issued invoice
- Auditable payment reversal & invoice balance restoration
- Role-based data isolation (Supplier vs Nursery vs Admin)
- Audit trail event logging (PAYMENT_RECORDED, PAYMENT_REVERSED)
- Full API endpoint integration (GET /api/payments, POST /api/payments, etc.)
"""

import unittest
import os
import sys
import json
import tempfile
import sqlite3
from decimal import Decimal

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models.database import get_connection, init_database
from app.services.payment_service import (
    record_payment,
    allocate_advance_payment,
    reverse_payment,
    get_payment_details,
    list_payments_for_user,
    get_invoice_payment_summary,
    quantize_currency
)


class TestPhase9PaymentManagement(unittest.TestCase):
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

        # Initialize database
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

    def login_user(self, username, password="password123"):
        resp = self.client.post('/api/auth/login', json={
            'username': username,
            'password': password
        })
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()['data']

    def test_01_seed_payment_and_initial_balance(self):
        """Test that demo payment PAY-2026-8760 was seeded and invoice INV-2026-8760 has correct balance."""
        conn = get_connection(self.db_path)
        try:
            summary = get_invoice_payment_summary(conn, "INV-2026-8760")
            self.assertIsNotNone(summary)
            self.assertEqual(summary['total_amount'], 41160.00)
            self.assertEqual(summary['total_paid'], 10500.00)
            self.assertEqual(summary['outstanding_balance'], 30660.00)
            self.assertEqual(summary['payment_status'], 'PARTIALLY_PAID')
            self.assertEqual(summary['allocations_count'], 1)
        finally:
            conn.close()

    def test_02_record_partial_payment(self):
        """Test recording a partial payment against INV-2026-8760 reduces balance accurately."""
        conn = get_connection(self.db_path)
        try:
            pay_data = {
                'invoice_id': 'INV-2026-8760',
                'amount': 10000.00,
                'payment_method': 'UPI',
                'reference_number': 'UPI-REF-99281726',
                'payment_date': '2026-10-18',
                'notes': 'Partial installment via UPI'
            }
            res = record_payment(conn, pay_data, self.supplier)
            self.assertIsNotNone(res)
            self.assertEqual(res['payment']['amount'], 10000.00)
            self.assertEqual(res['payment']['status'], 'RECORDED')

            # Verify updated balance
            summary = get_invoice_payment_summary(conn, "INV-2026-8760")
            self.assertEqual(summary['total_paid'], 20500.00)
            self.assertEqual(summary['outstanding_balance'], 20660.00)
            self.assertEqual(summary['payment_status'], 'PARTIALLY_PAID')
        finally:
            conn.close()

    def test_03_record_full_settlement(self):
        """Test paying the exact remaining balance marks invoice as PAID and outstanding balance to 0.00."""
        conn = get_connection(self.db_path)
        try:
            # Remaining balance on INV-2026-8760 is 30660.00
            pay_data = {
                'invoice_id': 'INV-2026-8760',
                'amount': 30660.00,
                'payment_method': 'BANK_TRANSFER',
                'reference_number': 'RTGS-HDFC-9918237',
                'payment_date': '2026-10-20',
                'notes': 'Final settlement in full'
            }
            res = record_payment(conn, pay_data, self.supplier)
            self.assertIsNotNone(res)

            summary = get_invoice_payment_summary(conn, "INV-2026-8760")
            self.assertEqual(summary['total_paid'], 41160.00)
            self.assertEqual(summary['outstanding_balance'], 0.00)
            self.assertEqual(summary['payment_status'], 'PAID')
        finally:
            conn.close()

    def test_04_reject_overpayment(self):
        """Test that payment amount exceeding invoice outstanding balance is strictly rejected."""
        conn = get_connection(self.db_path)
        try:
            # Current balance is 30660.00; attempt to pay 31000.00
            pay_data = {
                'invoice_id': 'INV-2026-8760',
                'amount': 31000.00,
                'payment_method': 'BANK_TRANSFER',
                'reference_number': 'OVERPAY-UTR-001'
            }
            with self.assertRaises(ValueError) as cm:
                record_payment(conn, pay_data, self.supplier)
            self.assertIn("Overpayment rejected", str(cm.exception))
        finally:
            conn.close()

    def test_05_reject_duplicate_reference(self):
        """Test that submitting a duplicate transaction reference is rejected."""
        conn = get_connection(self.db_path)
        try:
            # 'UTR982341092834' is already recorded on demo payment PAY-2026-8760
            pay_data = {
                'invoice_id': 'INV-2026-8760',
                'amount': 5000.00,
                'payment_method': 'BANK_TRANSFER',
                'reference_number': 'UTR982341092834'
            }
            with self.assertRaises(ValueError) as cm:
                record_payment(conn, pay_data, self.supplier)
            self.assertIn("already been recorded", str(cm.exception))
        finally:
            conn.close()

    def test_06_reject_zero_and_negative_amounts(self):
        """Test that zero and negative amounts are rejected."""
        conn = get_connection(self.db_path)
        try:
            for bad_amt in (0, -100, -0.01):
                pay_data = {
                    'invoice_id': 'INV-2026-8760',
                    'amount': bad_amt,
                    'reference_number': f'NEG-REF-{bad_amt}'
                }
                with self.assertRaises(ValueError) as cm:
                    record_payment(conn, pay_data, self.supplier)
                self.assertIn("strictly positive", str(cm.exception))
        finally:
            conn.close()

    def test_07_decimal_precision_paise(self):
        """Test safe decimal arithmetic avoiding IEEE floating-point errors."""
        val1 = quantize_currency("123.45")
        val2 = quantize_currency("67.89")
        sum_val = quantize_currency(val1 + val2)
        self.assertEqual(str(sum_val), "191.34")

        # Check half-up rounding
        round_up = quantize_currency("10.005")
        self.assertEqual(str(round_up), "10.01")

    def test_08_record_advance_payment(self):
        """Test recording an unallocated advance payment."""
        conn = get_connection(self.db_path)
        try:
            advance_data = {
                'order_id': 'ORD-8760',
                'amount': 15000.00,
                'payment_method': 'BANK_TRANSFER',
                'reference_number': 'ADV-NEFT-881920',
                'payment_type': 'ADVANCE_PAYMENT',
                'notes': 'Unallocated seasonal booking deposit'
            }
            res = record_payment(conn, advance_data, self.supplier)
            self.assertIsNotNone(res)
            self.assertEqual(res['payment']['amount'], 15000.00)
            self.assertEqual(res['payment']['unallocated_amount'], 15000.00)
            self.assertEqual(res['payment']['payment_type'], 'ADVANCE_PAYMENT')
            self.assertEqual(res['payment']['status'], 'RECORDED')
        finally:
            conn.close()

    def test_09_allocate_advance_to_invoice(self):
        """Test allocating an existing unallocated advance to an issued invoice."""
        conn = get_connection(self.db_path)
        try:
            # 1. Record an advance of ₹10,000
            advance_data = {
                'order_id': 'ORD-8760',
                'amount': 10000.00,
                'payment_method': 'BANK_TRANSFER',
                'reference_number': 'ADV-NEFT-994411',
                'payment_type': 'ADVANCE_PAYMENT'
            }
            res = record_payment(conn, advance_data, self.supplier)
            pay_id = res['payment']['id']

            # 2. Allocate ₹6,000 of the advance to INV-2026-8760
            alloc_res = allocate_advance_payment(conn, pay_id, "INV-2026-8760", 6000.00, self.supplier)
            self.assertEqual(alloc_res['allocated_amount'], 6000.00)
            self.assertEqual(alloc_res['remaining_unallocated_advance'], 4000.00)
            self.assertEqual(alloc_res['invoice_outstanding_balance'], 24660.00)

            # 3. Check invoice summary
            summary = get_invoice_payment_summary(conn, "INV-2026-8760")
            self.assertEqual(summary['total_paid'], 16500.00) # 10500 seeded + 6000 allocated
            self.assertEqual(summary['outstanding_balance'], 24660.00)
        finally:
            conn.close()

    def test_10_payment_reversal(self):
        """Test auditable payment reversal restores invoice balance and updates payment status."""
        conn = get_connection(self.db_path)
        try:
            # 1. Record payment of ₹5,000
            pay_data = {
                'invoice_id': 'INV-2026-8760',
                'amount': 5000.00,
                'payment_method': 'CHEQUE',
                'reference_number': 'CHQ-882199',
                'notes': 'Cheque payment pending clearance'
            }
            res = record_payment(conn, pay_data, self.supplier)
            pay_id = res['payment']['id']

            # Balance was 30660 - 5000 = 25660
            summary_before = get_invoice_payment_summary(conn, "INV-2026-8760")
            self.assertEqual(summary_before['outstanding_balance'], 25660.00)

            # 2. Reverse payment due to cheque bounce
            reversal_reason = "Cheque bounced due to signature mismatch on bank side."
            rev_res = reverse_payment(conn, pay_id, reversal_reason, self.supplier)
            self.assertEqual(rev_res['payment']['status'], 'REVERSED')
            self.assertEqual(rev_res['payment']['reversal_reason'], reversal_reason)

            # 3. Verify invoice balance is restored back to 30660.00
            summary_after = get_invoice_payment_summary(conn, "INV-2026-8760")
            self.assertEqual(summary_after['outstanding_balance'], 30660.00)
            self.assertEqual(summary_after['total_paid'], 10500.00)
        finally:
            conn.close()

    def test_11_role_isolation(self):
        """Test that cross-party users cannot view or reverse payments outside their business."""
        conn = get_connection(self.db_path)
        try:
            # Create a 4th user (an unrelated nursery)
            conn.execute(
                """INSERT INTO users (username, email, password_hash, role, business_name)
                   VALUES ('other_nursery', 'other@nursery.com', 'hash', 'NURSERY', 'Other Nursery LLC')"""
            )
            other_user = dict(conn.execute("SELECT * FROM users WHERE username = 'other_nursery'").fetchone())

            # Attempt to view PAY-2026-8760 belonging to nursery_amit and supplier_rajesh
            with self.assertRaises(PermissionError):
                get_payment_details(conn, "PAY-2026-8760", other_user)
        finally:
            conn.close()

    def test_12_audit_trail_logging(self):
        """Test that payment recording and reversal append immutable events to audit_events."""
        conn = get_connection(self.db_path)
        try:
            pay_data = {
                'invoice_id': 'INV-2026-8760',
                'amount': 2000.00,
                'payment_method': 'UPI',
                'reference_number': 'AUDIT-UPI-001'
            }
            res = record_payment(conn, pay_data, self.supplier)
            pay_id = res['payment']['id']

            reverse_payment(conn, pay_id, "Reversed for audit test validation.", self.supplier)

            # Query audit_events for ORD-8760
            events = conn.execute(
                "SELECT event_type, actor_role, justification FROM audit_events WHERE order_id = 'ORD-8760' ORDER BY id DESC"
            ).fetchall()

            event_types = [e['event_type'] for e in events]
            self.assertIn('PAYMENT_RECORDED', event_types)
            self.assertIn('PAYMENT_REVERSED', event_types)
        finally:
            conn.close()

    def test_13_api_endpoints(self):
        """Test Flask REST API routes for payments."""
        self.login_user('supplier_rajesh')

        # 1. GET /api/payments
        res = self.client.get('/api/payments')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data['success'])
        self.assertGreaterEqual(json_data['count'], 1)
        self.assertIn('kpi', json_data)

        # 2. GET /api/invoices/INV-2026-8760/payments
        res_inv = self.client.get('/api/invoices/INV-2026-8760/payments')
        self.assertEqual(res_inv.status_code, 200)
        inv_data = res_inv.get_json()
        self.assertEqual(inv_data['data']['invoice_number'], 'INV-2026-8760')

        # 3. POST /api/payments
        new_pay_payload = {
            'invoice_id': 'INV-2026-8760',
            'amount': 1500.00,
            'payment_method': 'BANK_TRANSFER',
            'reference_number': 'API-TEST-UTR-99182',
            'notes': 'API test payment'
        }
        res_post = self.client.post('/api/payments', json=new_pay_payload)
        self.assertEqual(res_post.status_code, 201)
        created_data = res_post.get_json()
        self.assertTrue(created_data['success'])
        pay_id = created_data['data']['payment']['id']

        # 4. POST /api/payments/<id>/reverse
        res_rev = self.client.post(f'/api/payments/{pay_id}/reverse', json={
            'reason': 'API reversal validation test'
        })
        self.assertEqual(res_rev.status_code, 200)
        rev_data = res_rev.get_json()
        self.assertEqual(rev_data['data']['payment']['status'], 'REVERSED')


if __name__ == '__main__':
    unittest.main()
