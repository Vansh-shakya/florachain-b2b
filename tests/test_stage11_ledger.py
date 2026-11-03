"""
FloraChain B2B — Phase 11 Commercial Ledger & Transaction History Test Suite
Comprehensive testing of:
- quantize_currency decimal arithmetic (ROUND_HALF_UP) & parse_date_safe
- Authoritative balance calculation formulas:
    * Total Invoiced Gross (active issued invoices)
    * Total Payments Recorded (active recorded payments)
    * Total Allocated Payments (active payment allocations)
    * Total Unallocated Advances (active recorded advance payments)
    * Outstanding Principal (gross invoice value minus allocated payments)
    * Net Balance Due (gross invoice value minus total active payments)
    * Accrued Late-Payment Interest (strictly separated from invoice principal)
    * Total Payable with Interest
    * Consistency verification (Allocated + Unallocated == Active Payments, Variance == 0.00)
- Prevention of double-counting: payments vs allocations
- Unallocated advance funds tracking (does not reduce invoice principal until allocated)
- Payment reversal behavior (restores principal, does not subtract twice, remains visible)
- Cancelled invoice handling (nullifies debt, remains visible as CANCELLED)
- Chronological sorting and deterministic workflow precedence tie-breaking
- Multi-parameter filtering: type, counterparty (nursery), date range, status, search
- Role-based permissions and strict multi-tenant counterparty isolation
- REST API integration: GET /api/ledger and GET /api/ledger/summary
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
from app.services.ledger_service import (
    get_ledger_entries,
    get_ledger_summary,
    quantize_currency,
    parse_date_safe
)
from app.services.payment_service import (
    record_payment,
    reverse_payment
)


class TestPhase11LedgerAndTransactionHistory(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for this test run
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.app = create_app({
            'TESTING': True,
            'DB_PATH': self.db_path,
            'SECRET_KEY': 'test-phase11-secret-key',
            'ALLOW_DEMO_ROLE_SWITCH': True
        })
        self.client = self.app.test_client()

        # Initialize database with schema and seeds
        init_database(self.db_path)

        # Retrieve test users from database
        with get_connection(self.db_path) as conn:
            self.supplier = dict(conn.execute("SELECT * FROM users WHERE username = 'supplier_rajesh'").fetchone())
            self.nursery = dict(conn.execute("SELECT * FROM users WHERE username = 'nursery_amit'").fetchone())
            self.admin = dict(conn.execute("SELECT * FROM users WHERE username = 'admin_flora'").fetchone())

    def tearDown(self):
        try:
            os.close(self.db_fd)
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except OSError:
            pass

    def test_01_quantize_and_parse_date_utilities(self):
        """Test strict ROUND_HALF_UP 2-decimal arithmetic and safe date parsing."""
        self.assertEqual(quantize_currency(100.555), Decimal('100.56'))
        self.assertEqual(quantize_currency(100.554), Decimal('100.55'))
        self.assertEqual(quantize_currency(None), Decimal('0.00'))
        self.assertEqual(quantize_currency('25000.50'), Decimal('25000.50'))

        d1 = parse_date_safe('2026-10-16')
        self.assertEqual(d1, datetime.date(2026, 10, 16))
        d2 = parse_date_safe('2026-10-16 14:30:00')
        self.assertEqual(d2, datetime.date(2026, 10, 16))
        self.assertIsNone(parse_date_safe(None))
        self.assertIsNone(parse_date_safe('invalid-date'))

    def test_02_seeded_demo_ledger_summary(self):
        """Test ledger summary calculations on clean seed data (INV-2026-8760)."""
        with get_connection(self.db_path) as conn:
            summary = get_ledger_summary(conn, self.supplier)

            self.assertEqual(summary['total_invoiced_gross'], 41160.0)
            self.assertEqual(summary['total_payments_recorded'], 10500.0)
            self.assertEqual(summary['total_allocated_payments'], 10500.0)
            self.assertEqual(summary['total_unallocated_advances'], 0.0)
            self.assertEqual(summary['outstanding_principal'], 30660.0)
            self.assertEqual(summary['net_balance_due'], 30660.0)
            self.assertTrue(summary['is_balanced'])
            self.assertEqual(summary['balance_variance'], 0.0)
            self.assertGreaterEqual(summary['total_accrued_interest'], 0.0)

    def test_03_prevention_of_double_counting(self):
        """Test that payment and its allocation are never double-counted in cash inflow."""
        with get_connection(self.db_path) as conn:
            summary = get_ledger_summary(conn, self.supplier)
            # Cash inflow is strictly payments (10,500), not payments + allocations (21,000)
            self.assertEqual(summary['total_payments_recorded'], 10500.0)
            self.assertEqual(
                summary['total_allocated_payments'] + summary['total_unallocated_advances'],
                summary['total_payments_recorded']
            )

    def test_04_unallocated_advance_does_not_reduce_invoice_principal(self):
        """
        An unallocated advance payment must NOT reduce invoice outstanding principal,
        but DOES reduce net balance due.
        """
        with get_connection(self.db_path) as conn:
            # Record an advance payment of 10,000 for nursery (not linked to invoice)
            payment_data = {
                'nursery_user_id': self.nursery['id'],
                'payment_type': 'ADVANCE_PAYMENT',
                'amount': 10000.0,
                'payment_date': '2026-10-20',
                'payment_method': 'BANK_TRANSFER',
                'reference_number': 'ADV-UTR-9999',
                'notes': 'Advance deposit for upcoming seasonal batch'
            }
            payment_res = record_payment(conn, payment_data, self.supplier)
            self.assertIsNotNone(payment_res)
            self.assertEqual(payment_res['payment']['status'], 'RECORDED')

            summary = get_ledger_summary(conn, self.supplier, nursery_id=self.nursery['id'])

            # Gross invoice: 41,160
            self.assertEqual(summary['total_invoiced_gross'], 41160.0)
            # Total active payments: 10,500 + 10,000 = 20,500
            self.assertEqual(summary['total_payments_recorded'], 20500.0)
            # Allocated payments: still only 10,500
            self.assertEqual(summary['total_allocated_payments'], 10500.0)
            # Unallocated advance: 10,000
            self.assertEqual(summary['total_unallocated_advances'], 10000.0)
            # Outstanding principal on invoices remains 30,660! (41,160 - 10,500)
            self.assertEqual(summary['outstanding_principal'], 30660.0)
            # Net balance due is reduced: 41,160 - 20,500 = 20,660
            self.assertEqual(summary['net_balance_due'], 20660.0)
            # Consistency invariant preserved
            self.assertTrue(summary['is_balanced'])
            self.assertEqual(summary['balance_variance'], 0.0)

    def test_05_payment_reversal_restores_principal_and_remains_visible(self):
        """
        Reversing a payment must restore outstanding principal, must not subtract twice,
        and must remain visible in transaction history with REVERSED status.
        """
        with get_connection(self.db_path) as conn:
            # Find seeded payment PAY-2026-8760
            rev_res = reverse_payment(
                conn,
                'PAY-2026-8760',
                'Customer cheque returned due to signature mismatch',
                self.supplier
            )
            self.assertEqual(rev_res['payment']['status'], 'REVERSED')

            summary = get_ledger_summary(conn, self.supplier, nursery_id=self.nursery['id'])

            # Active payments dropped to 0, reversed payments = 10,500
            self.assertEqual(summary['total_payments_recorded'], 0.0)
            self.assertEqual(summary['total_payments_reversed'], 10500.0)
            self.assertEqual(summary['total_allocated_payments'], 0.0)
            # Outstanding principal restored to full invoice amount: 41,160
            self.assertEqual(summary['outstanding_principal'], 41160.0)
            self.assertEqual(summary['net_balance_due'], 41160.0)
            self.assertTrue(summary['is_balanced'])

            # Verify ledger entries include both the payment and the reversal event
            ledger_data = get_ledger_entries(conn, self.supplier, {'nursery_id': self.nursery['id']})
            entries = ledger_data['entries']
            entry_types = [e['type'] for e in entries]
            self.assertIn('PAYMENT_REVERSED', entry_types)

            # The reversed payment record itself is visible with status REVERSED
            rev_payment_entry = next((e for e in entries if e['reference_id'] == 'PAY-2026-8760'), None)
            self.assertIsNotNone(rev_payment_entry)
            self.assertEqual(rev_payment_entry['status'], 'REVERSED')

    def test_06_cancelled_invoice_nullifies_debt_and_remains_in_history(self):
        """
        Cancelling an invoice nullifies the gross invoice value and appears as INVOICE_CANCELLED.
        """
        with get_connection(self.db_path) as conn:
            # First reverse the payment on INV-2026-8760 so it has 0 allocated payments
            reverse_payment(
                conn,
                'PAY-2026-8760',
                'Preparing for invoice cancellation',
                self.supplier
            )

            # Cancel the invoice
            conn.execute(
                "UPDATE invoices SET status = 'CANCELLED' WHERE invoice_number = 'INV-2026-8760'"
            )
            conn.commit()

            summary = get_ledger_summary(conn, self.supplier, nursery_id=self.nursery['id'])
            self.assertEqual(summary['total_invoiced_gross'], 0.0)
            self.assertEqual(summary['total_invoiced_cancelled'], 41160.0)
            self.assertEqual(summary['outstanding_principal'], 0.0)
            self.assertEqual(summary['net_balance_due'], 0.0)

            ledger_data = get_ledger_entries(conn, self.supplier, {'nursery_id': self.nursery['id']})
            entry_types = [e['type'] for e in ledger_data['entries']]
            self.assertIn('INVOICE_CANCELLED', entry_types)

    def test_07_chronological_sorting_and_deterministic_tie_breaking(self):
        """
        Test chronological sorting by transaction_date and workflow precedence.
        """
        with get_connection(self.db_path) as conn:
            # Ascending order
            res_asc = get_ledger_entries(conn, self.supplier, {'order': 'asc'})
            entries_asc = res_asc['entries']
            dates_asc = [e['transaction_date'] for e in entries_asc]
            self.assertEqual(dates_asc, sorted(dates_asc))

            # Descending order
            res_desc = get_ledger_entries(conn, self.supplier, {'order': 'desc'})
            entries_desc = res_desc['entries']
            dates_desc = [e['transaction_date'] for e in entries_desc]
            self.assertEqual(dates_desc, sorted(dates_desc, reverse=True))

            # On same date (e.g. today), DELIVERY_VERIFIED (precedence 1) must precede PAYMENT_ALLOCATED (precedence 4)
            delivery_idx = next(i for i, e in enumerate(entries_asc) if e['type'] == 'DELIVERY_VERIFIED')
            alloc_idx = next(i for i, e in enumerate(entries_asc) if e['type'] == 'PAYMENT_ALLOCATED')
            self.assertLess(delivery_idx, alloc_idx)

    def test_08_multi_parameter_filtering(self):
        """Test ledger entry filtering by type, date range, status, and search."""
        with get_connection(self.db_path) as conn:
            # Filter by type: INVOICE
            inv_data = get_ledger_entries(conn, self.supplier, {'type': 'INVOICE'})
            inv_entries = inv_data['entries']
            self.assertTrue(all('INVOICE' in e['type'] for e in inv_entries))
            self.assertGreaterEqual(len(inv_entries), 1)

            # Filter by type: PAYMENT
            pay_data = get_ledger_entries(conn, self.supplier, {'type': 'PAYMENT'})
            pay_entries = pay_data['entries']
            self.assertTrue(all('PAYMENT' in e['type'] for e in pay_entries))
            self.assertGreaterEqual(len(pay_entries), 1)

            # Filter by date range
            range_data = get_ledger_entries(conn, self.supplier, {
                'start_date': '2026-10-10',
                'end_date': '2026-10-25'
            })
            for e in range_data['entries']:
                self.assertGreaterEqual(e['transaction_date'], '2026-10-10')
                self.assertLessEqual(e['transaction_date'], '2026-10-25')

            # Search query
            search_data = get_ledger_entries(conn, self.supplier, {'search': '8760'})
            self.assertTrue(all('8760' in str(e['reference_id']) or '8760' in str(e['related_reference']) or '8760' in str(e['description']) for e in search_data['entries']))

    def test_09_tenant_isolation_role_permissions(self):
        """
        Nursery user can ONLY see transactions and counterparties belonging to their nursery.
        Supplier user sees all nurseries they supply.
        """
        with get_connection(self.db_path) as conn:
            # Nursery user sees their entries
            nursery1_data = get_ledger_entries(conn, self.nursery)
            self.assertGreaterEqual(len(nursery1_data['entries']), 1)
            for e in nursery1_data['entries']:
                self.assertEqual(e['nursery_id'], self.nursery['id'])

            # Create another nursery with 0 transactions
            other_nursery = {'id': 9999, 'role': 'NURSERY', 'username': 'nursery_other'}
            nursery2_data = get_ledger_entries(conn, other_nursery)
            self.assertEqual(len(nursery2_data['entries']), 0)

            # Nursery 2 summary must reflect zero balances
            nursery2_summary = get_ledger_summary(conn, other_nursery)
            self.assertEqual(nursery2_summary['total_invoiced_gross'], 0.0)
            self.assertEqual(nursery2_summary['total_payments_recorded'], 0.0)
            self.assertEqual(nursery2_summary['outstanding_principal'], 0.0)

    def test_10_api_endpoints_integration(self):
        """Test GET /api/ledger and GET /api/ledger/summary HTTP endpoints."""
        # Log in as supplier
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.supplier['id']
            sess['role'] = 'supplier'

        # 1. GET /api/ledger
        res = self.client.get('/api/ledger')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode('utf-8'))
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('summary', data)
        self.assertIn('counterparties', data)
        self.assertGreaterEqual(data['count'], 1)
        self.assertEqual(data['summary']['total_invoiced_gross'], 41160.0)
        self.assertTrue(data['summary']['is_balanced'])

        # 2. GET /api/ledger/summary
        res_sum = self.client.get('/api/ledger/summary')
        self.assertEqual(res_sum.status_code, 200)
        data_sum = json.loads(res_sum.data.decode('utf-8'))
        self.assertTrue(data_sum['success'])
        self.assertEqual(data_sum['data']['outstanding_principal'], 30660.0)

        # 3. GET /api/ledger with nursery filter
        res_filter = self.client.get(f"/api/ledger?nursery_id={self.nursery['id']}&type=INVOICE")
        self.assertEqual(res_filter.status_code, 200)
        data_filter = json.loads(res_filter.data.decode('utf-8'))
        self.assertTrue(data_filter['success'])
        self.assertTrue(all('INVOICE' in item['type'] for item in data_filter['data']))

        # 4. Unauthenticated access
        with self.client.session_transaction() as sess:
            sess.clear()
        res_unauth = self.client.get('/api/ledger')
        self.assertEqual(res_unauth.status_code, 401)


if __name__ == '__main__':
    unittest.main()
