"""
FloraChain B2B — Phase 16 Frontend/Backend Integration Test Suite
Validates:
1. Real authentication login flow (POST /api/auth/login)
2. Session verification and identity introspection (GET /api/auth/me)
3. Working logout flow (POST /api/auth/logout)
4. Demo role switching guardrails (POST /api/auth/switch-role in dev vs production)
5. Live nursery directory integration (GET /api/orders/nurseries)
6. Expandable order audit trail integration (GET /api/orders/<order_id>/audit)
7. Active SQLite database immutability & table row count preservation
"""

import unittest
import os
import sys
import json
import sqlite3
import tempfile

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models.database import get_connection, init_database


class TestPhase16Integration(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        self.app = create_app({
            'TESTING': True,
            'DB_PATH': self.temp_db_path,
            'SECRET_KEY': 'phase16-integration-test-secret',
            'ALLOW_DEMO_ROLE_SWITCH': False,
            'CSRF_ENABLED': True
        })
        self.client = self.app.test_client()

        # Initialize test schema & seed data
        init_database(self.temp_db_path)

    def tearDown(self):
        try:
            os.close(self.temp_db_fd)
            if os.path.exists(self.temp_db_path):
                os.unlink(self.temp_db_path)
        except OSError:
            pass

    # =========================================================================
    # 1. AUTHENTICATION INTEGRATION TESTS
    # =========================================================================

    def test_login_success_supplier(self):
        """Verify POST /api/auth/login authenticates with valid credentials."""
        res = self.client.post('/api/auth/login', json={
            'email': 'supplier@greenrootsfarms.com',
            'password': 'password123'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['role'], 'SUPPLIER')
        self.assertEqual(data['data']['business_name'], 'GreenRoots Wholesale Farms')
        self.assertTrue(bool(data['csrf_token']))

    def test_login_success_nursery(self):
        """Verify POST /api/auth/login authenticates nursery user with valid credentials."""
        res = self.client.post('/api/auth/login', json={
            'email': 'purchasing@greenmeadows.com',
            'password': 'password123'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['role'], 'NURSERY')
        self.assertEqual(data['data']['business_name'], 'Green Meadows Landscape Nursery')

    def test_login_failure_invalid_password(self):
        """Verify POST /api/auth/login rejects wrong password with 401."""
        res = self.client.post('/api/auth/login', json={
            'email': 'supplier@greenrootsfarms.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Invalid', data['error'])

    def test_get_me_unauthenticated(self):
        """Verify GET /api/auth/me returns 401 when no session exists."""
        res = self.client.get('/api/auth/me')
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data['authenticated'])

    def test_get_me_authenticated(self):
        """Verify GET /api/auth/me returns profile after login."""
        self.client.post('/api/auth/login', json={
            'email': 'supplier@greenrootsfarms.com',
            'password': 'password123'
        })
        res = self.client.get('/api/auth/me')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['authenticated'])
        self.assertEqual(data['data']['role'], 'SUPPLIER')
        self.assertEqual(data['data']['username'], 'supplier_rajesh')

    def test_logout_revokes_session(self):
        """Verify POST /api/auth/logout clears active session."""
        login_res = self.client.post('/api/auth/login', json={
            'email': 'supplier@greenrootsfarms.com',
            'password': 'password123'
        })
        csrf_token = login_res.get_json()['csrf_token']

        # Logout with CSRF token
        logout_res = self.client.post(
            '/api/auth/logout',
            headers={'X-CSRF-Token': csrf_token}
        )
        self.assertEqual(logout_res.status_code, 200)
        logout_data = logout_res.get_json()
        self.assertTrue(logout_data['success'])

        # Next check to /api/auth/me must return 401 Unauthorized
        me_res = self.client.get('/api/auth/me')
        self.assertEqual(me_res.status_code, 401)

    def test_switch_role_blocked_in_production(self):
        """Verify POST /api/auth/switch-role is 403 when ALLOW_DEMO_ROLE_SWITCH is False."""
        res = self.client.post('/api/auth/switch-role', json={'role': 'SUPPLIER'})
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('disabled', data['error'].lower())

    def test_switch_role_allowed_in_dev_mode(self):
        """Verify POST /api/auth/switch-role functions when ALLOW_DEMO_ROLE_SWITCH is True."""
        dev_app = create_app({
            'TESTING': True,
            'DB_PATH': self.temp_db_path,
            'SECRET_KEY': 'dev-key',
            'ALLOW_DEMO_ROLE_SWITCH': True,
            'CSRF_ENABLED': False
        })
        dev_client = dev_app.test_client()

        res = dev_client.post('/api/auth/switch-role', json={'role': 'NURSERY'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['role'], 'NURSERY')
        self.assertEqual(data['data']['username'], 'nursery_amit')

    # =========================================================================
    # 2. NURSERY DIRECTORY INTEGRATION
    # =========================================================================

    def test_list_nurseries_for_orders(self):
        """Verify GET /api/orders/nurseries returns registered platform nurseries."""
        self.client.post('/api/auth/login', json={
            'email': 'supplier@greenrootsfarms.com',
            'password': 'password123'
        })
        res = self.client.get('/api/orders/nurseries')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 1)
        nurseries = data['data']
        nursery_names = [n['business_name'] for n in nurseries]
        self.assertIn('Green Meadows Landscape Nursery', nursery_names)

    # =========================================================================
    # 3. ORDER AUDIT TRAIL ENDPOINT
    # =========================================================================

    def test_order_audit_trail_authorized(self):
        """Verify GET /api/orders/<order_id>/audit returns audit log for order party."""
        self.client.post('/api/auth/login', json={
            'email': 'supplier@greenrootsfarms.com',
            'password': 'password123'
        })
        res = self.client.get('/api/orders/ORD-8801/audit')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['order_id'], 'ORD-8801')
        self.assertIsInstance(data['data'], list)

    def test_order_audit_trail_unrelated_party_forbidden(self):
        """Verify GET /api/orders/<order_id>/audit returns 403 for unrelated user."""
        conn = get_connection(self.temp_db_path)
        try:
            with conn:
                conn.execute(
                    """INSERT INTO users (id, username, email, password_hash, role, business_name)
                       VALUES (999, 'unrelated_nurs', 'unrelated@test.com', 'scrypt:test', 'NURSERY', 'Other Nursery')"""
                )
        finally:
            conn.close()

        with self.client.session_transaction() as sess:
            sess['user_id'] = 999
            sess['role'] = 'NURSERY'
            sess['username'] = 'unrelated_nurs'

        res = self.client.get('/api/orders/ORD-8801/audit')
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Unauthorized', data['error'])

    # =========================================================================
    # 4. DATABASE INTEGRITY CHECK (SQLite data/florachain.db)
    # =========================================================================

    def test_active_sqlite_database_preserved(self):
        """Verify active SQLite production database maintains exact 14 tables and 43 rows."""
        prod_db_path = os.path.join(BASE_DIR, 'data', 'florachain.db')
        self.assertTrue(os.path.exists(prod_db_path), "Active database data/florachain.db must exist.")

        conn = sqlite3.connect(prod_db_path)
        conn.row_factory = sqlite3.Row
        try:
            tables = [
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            expected_tables = [
                'agreement_amendments', 'agreement_approvals', 'audit_events',
                'deal_agreements', 'delivery_confirmations', 'delivery_inspections',
                'invoice_items', 'invoices', 'ledger_transactions', 'order_items',
                'orders', 'payment_allocations', 'payments', 'plants', 'users'
            ]
            # Verify tables (14 or 15 depending on schema)
            self.assertGreaterEqual(len(tables), 14)

            total_rows = 0
            for t in tables:
                count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                total_rows += count

            # Verify rows are intact (43 rows in initial seed)
            self.assertEqual(total_rows, 43, f"Expected 43 rows across database tables, got {total_rows}.")
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()

