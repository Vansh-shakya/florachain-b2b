"""
FloraChain B2B — Phase 12 Nursery Dashboard Test Suite
Comprehensive testing of:
- Nursery Dashboard Service Layer:
    * get_nursery_dashboard_data for authenticated nursery buyer
    * Correct aggregation of orders, inbound shipments, invoices, due dates, agreements, ledger
    * Authoritative financial balances (Gross Invoiced, Allocated Payments, Advances, Principal, Net Due, Accrued Interest)
    * Strict separation of interest from invoice principal
    * Strict separation of unallocated advances from invoice payments
    * Clean zero-state handling for new/empty nursery without crashes or invented numbers
    * Multi-tenant counterparty isolation (no cross-nursery data leakage)
    * Role-based access control (SUPPLIER rejected, NURSERY and ADMIN permitted)
- Nursery Routes API Integration:
    * GET /api/nursery/dashboard
    * 401 for unauthenticated requests
    * 403 Forbidden for SUPPLIER role
    * 200 OK for authenticated NURSERY role
    * 200 OK for ADMIN role
"""

import unittest
import os
import sys
import json
import tempfile
from decimal import Decimal

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models.database import get_connection, init_database
from app.services.nursery_dashboard_service import get_nursery_dashboard_data
from app.services.payment_service import record_payment


class TestPhase12NurseryDashboard(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for this test run
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.app = create_app({
            'TESTING': True,
            'DB_PATH': self.db_path,
            'SECRET_KEY': 'test-phase12-secret-key',
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

    def test_01_nursery_dashboard_seeded_data(self):
        """Test nursery dashboard metrics aggregation on seed data (ORD-8760, INV-2026-8760)."""
        with get_connection(self.db_path) as conn:
            dash = get_nursery_dashboard_data(conn, self.nursery)

            # Profile verification
            self.assertEqual(dash['profile']['id'], self.nursery['id'])
            self.assertEqual(dash['profile']['username'], 'nursery_amit')
            self.assertEqual(dash['profile']['business_name'], 'Green Meadows Landscape Nursery')

            # Metrics verification
            metrics = dash['metrics']
            self.assertGreaterEqual(metrics['total_orders'], 1)
            self.assertGreaterEqual(metrics['total_invoices'], 1)
            self.assertEqual(metrics['total_invoiced_gross'], 41160.0)
            self.assertEqual(metrics['total_payments_recorded'], 10500.0)
            self.assertEqual(metrics['total_allocated_payments'], 10500.0)
            self.assertEqual(metrics['total_unallocated_advances'], 0.0)
            self.assertEqual(metrics['outstanding_principal'], 30660.0)
            self.assertEqual(metrics['net_balance_due'], 30660.0)
            self.assertTrue(metrics['is_balanced'])

            # List collections verification
            self.assertIsInstance(dash['inbound_tasks'], list)
            self.assertIsInstance(dash['recent_orders'], list)
            self.assertGreaterEqual(len(dash['recent_orders']), 1)
            order_ids = [o['order_id'] for o in dash['recent_orders']]
            self.assertIn('ORD-8760', order_ids)

            self.assertIsInstance(dash['invoices'], list)
            self.assertGreaterEqual(len(dash['invoices']), 1)
            inv = dash['invoices'][0]
            self.assertEqual(inv['invoice_number'], 'INV-2026-8760')
            self.assertEqual(inv['outstanding_principal'], 30660.0)
            self.assertIn('due_status', inv)
            self.assertIn('accrued_interest', inv)

            self.assertIsInstance(dash['recent_transactions'], list)
            self.assertGreaterEqual(len(dash['recent_transactions']), 1)

            self.assertIsInstance(dash['agreements'], list)
            self.assertGreaterEqual(len(dash['agreements']), 1)
            agr_refs = [a['agreement_ref'] for a in dash['agreements']]
            self.assertTrue(any('8760' in ref for ref in agr_refs))

    def test_02_empty_state_for_clean_nursery(self):
        """Test clean empty state for a nursery with 0 orders, invoices, or transactions."""
        clean_nursery = {
            'id': 7777,
            'username': 'new_retail_nursery',
            'role': 'NURSERY',
            'business_name': 'Fresh Blooms Center'
        }

        with get_connection(self.db_path) as conn:
            dash = get_nursery_dashboard_data(conn, clean_nursery)

            self.assertEqual(dash['profile']['username'], 'new_retail_nursery')
            self.assertEqual(dash['profile']['business_name'], 'Fresh Blooms Center')

            metrics = dash['metrics']
            self.assertEqual(metrics['total_orders'], 0)
            self.assertEqual(metrics['active_orders'], 0)
            self.assertEqual(metrics['inbound_tasks_count'], 0)
            self.assertEqual(metrics['total_invoices'], 0)
            self.assertEqual(metrics['total_invoiced_gross'], 0.0)
            self.assertEqual(metrics['total_payments_recorded'], 0.0)
            self.assertEqual(metrics['total_allocated_payments'], 0.0)
            self.assertEqual(metrics['total_unallocated_advances'], 0.0)
            self.assertEqual(metrics['outstanding_principal'], 0.0)
            self.assertEqual(metrics['net_balance_due'], 0.0)
            self.assertEqual(metrics['total_accrued_interest'], 0.0)
            self.assertEqual(metrics['total_amount_payable_with_interest'], 0.0)
            self.assertTrue(metrics['is_balanced'])

            self.assertEqual(dash['inbound_tasks'], [])
            self.assertEqual(dash['recent_orders'], [])
            self.assertEqual(dash['invoices'], [])
            self.assertEqual(dash['recent_transactions'], [])
            self.assertEqual(dash['agreements'], [])

    def test_03_role_authorization_and_permission_enforcement(self):
        """Test that get_nursery_dashboard_data strictly enforces NURSERY and ADMIN roles."""
        with get_connection(self.db_path) as conn:
            # 1. Unauthenticated / None user
            with self.assertRaises(PermissionError):
                get_nursery_dashboard_data(conn, None)

            # 2. Supplier user role
            with self.assertRaises(PermissionError):
                get_nursery_dashboard_data(conn, self.supplier)

            # 3. Arbitrary invalid role
            with self.assertRaises(PermissionError):
                get_nursery_dashboard_data(conn, {'id': 99, 'role': 'DRIVER', 'username': 'driver_john'})

            # 4. Admin role is allowed
            admin_dash = get_nursery_dashboard_data(conn, self.admin)
            self.assertIsNotNone(admin_dash)
            self.assertIn('metrics', admin_dash)

    def test_04_multi_tenant_counterparty_isolation(self):
        """Test that nursery 1 cannot see any orders, invoices, or transactions belonging to nursery 2."""
        with get_connection(self.db_path) as conn:
            # Insert a second nursery user
            conn.execute("""
                INSERT INTO users (id, username, email, password_hash, role, business_name)
                VALUES (202, 'nursery_bloom', 'bloom@example.com', 'hash', 'NURSERY', 'Bloom Valley Nursery')
            """)
            nursery2 = {'id': 202, 'username': 'nursery_bloom', 'role': 'NURSERY', 'business_name': 'Bloom Valley Nursery'}

            # Insert an order and invoice for Nursery 2
            conn.execute("""
                INSERT INTO orders (id, supplier_user_id, nursery_user_id, status, variety, ordered_qty, unit_price, truck_no, driver_info, created_at)
                VALUES ('ORD-BLOOM-01', ?, 202, 'CONFIRMED', 'Red Roses', 300, 50.0, 'TRUCK-99', 'Driver Raj', '2026-11-01 10:00:00')
            """, (self.supplier['id'],))
            conn.execute("""
                INSERT INTO invoices (id, invoice_number, order_id, supplier_user_id, nursery_user_id, invoice_date, subtotal, total_amount, total_quantity, status, created_by_user_id)
                VALUES ('INV-BLOOM-ID-01', 'INV-BLOOM-01', 'ORD-BLOOM-01', ?, 202, '2026-11-01', 15000.0, 15000.0, 300, 'ISSUED', ?)
            """, (self.supplier['id'], self.supplier['id']))
            conn.commit()

            # Dashboard for Nursery 1 (Amit) must not contain Nursery 2's order or invoice
            dash1 = get_nursery_dashboard_data(conn, self.nursery)
            order_ids_1 = [o['order_id'] for o in dash1['recent_orders']]
            inv_nos_1 = [i['invoice_number'] for i in dash1['invoices']]
            self.assertNotIn('ORD-BLOOM-01', order_ids_1)
            self.assertNotIn('INV-BLOOM-01', inv_nos_1)

            # Dashboard for Nursery 2 (Bloom) must contain only its own records
            dash2 = get_nursery_dashboard_data(conn, nursery2)
            order_ids_2 = [o['order_id'] for o in dash2['recent_orders']]
            inv_nos_2 = [i['invoice_number'] for i in dash2['invoices']]
            self.assertIn('ORD-BLOOM-01', order_ids_2)
            self.assertIn('INV-BLOOM-01', inv_nos_2)
            self.assertNotIn('ORD-8760', order_ids_2)
            self.assertNotIn('INV-2026-8760', inv_nos_2)

    def test_05_advance_payment_and_interest_separation(self):
        """Test that unallocated advances and accrued interest are strictly separated from principal."""
        with get_connection(self.db_path) as conn:
            # Record an unallocated advance payment of Rs 5,000 for Nursery Amit
            adv_data = {
                'payment_number': 'PAY-ADV-TEST-01',
                'nursery_user_id': self.nursery['id'],
                'amount': 5000.0,
                'payment_date': '2026-11-02',
                'payment_method': 'BANK_TRANSFER',
                'payment_type': 'ADVANCE_PAYMENT',
                'reference_number': 'NEFT-ADV-9988',
                'notes': 'Advance for future plant deliveries'
            }
            record_payment(conn, adv_data, self.supplier)

            # Fetch nursery dashboard
            dash = get_nursery_dashboard_data(conn, self.nursery)
            metrics = dash['metrics']

            # Gross is 41160.0
            self.assertEqual(metrics['total_invoiced_gross'], 41160.0)
            # Total active payments = 10500.0 + 5000.0 = 15500.0
            self.assertEqual(metrics['total_payments_recorded'], 15500.0)
            # Allocated payments remain 10500.0 (advance is unallocated)
            self.assertEqual(metrics['total_allocated_payments'], 10500.0)
            # Unallocated advance is 5000.0
            self.assertEqual(metrics['total_unallocated_advances'], 5000.0)
            # Outstanding principal on invoice is unchanged at 30660.0
            self.assertEqual(metrics['outstanding_principal'], 30660.0)
            # Net balance due = 30660.0 - 5000.0 = 25660.0
            self.assertEqual(metrics['net_balance_due'], 25660.0)
            # Accrued interest is tracked separately
            self.assertGreaterEqual(metrics['total_accrued_interest'], 0.0)
            self.assertTrue(metrics['is_balanced'])

    def test_06_api_endpoint_role_restrictions(self):
        """Test GET /api/nursery/dashboard HTTP route authentication and RBAC."""
        # 1. Unauthenticated request -> 401 Unauthorized
        res_unauth = self.client.get('/api/nursery/dashboard')
        self.assertEqual(res_unauth.status_code, 401)
        data_unauth = json.loads(res_unauth.data.decode('utf-8'))
        self.assertFalse(data_unauth['success'])

        # 2. Supplier request -> 403 Forbidden
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.supplier['id']
            sess['role'] = 'supplier'

        res_supplier = self.client.get('/api/nursery/dashboard')
        self.assertEqual(res_supplier.status_code, 403)
        data_supplier = json.loads(res_supplier.data.decode('utf-8'))
        self.assertFalse(data_supplier['success'])
        self.assertIn("Access denied", data_supplier['error'])

        # 3. Nursery request -> 200 OK
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.nursery['id']
            sess['role'] = 'nursery'

        res_nursery = self.client.get('/api/nursery/dashboard')
        self.assertEqual(res_nursery.status_code, 200)
        data_nursery = json.loads(res_nursery.data.decode('utf-8'))
        self.assertTrue(data_nursery['success'])
        self.assertEqual(data_nursery['data']['profile']['username'], 'nursery_amit')
        self.assertIn('metrics', data_nursery['data'])
        self.assertIn('inbound_tasks', data_nursery['data'])
        self.assertIn('recent_orders', data_nursery['data'])
        self.assertIn('invoices', data_nursery['data'])
        self.assertIn('agreements', data_nursery['data'])
        self.assertIn('recent_transactions', data_nursery['data'])
        self.assertEqual(data_nursery['data']['metrics']['outstanding_principal'], 30660.0)

        # 4. Admin request -> 200 OK
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin['id']
            sess['role'] = 'admin'

        res_admin = self.client.get('/api/nursery/dashboard')
        self.assertEqual(res_admin.status_code, 200)
        data_admin = json.loads(res_admin.data.decode('utf-8'))
        self.assertTrue(data_admin['success'])


if __name__ == '__main__':
    unittest.main()
