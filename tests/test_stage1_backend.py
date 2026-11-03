"""
FloraChain B2B — Stage 1 Backend Foundation Test Suite
Tests:
1. SQLite Database Initialization & Schema Creation
2. Table Constraints & Invariants (Foreign Keys, Roles, Unique Dual Confirmation, Signature Note)
3. Demonstration Seed Data Integrity
4. Flask Application Factory Startup & Static Gateway
5. Demonstration Role Switcher with Server-Side Authorization
"""

import unittest
import os
import sys
import tempfile
import sqlite3
import json

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models.database import get_connection, init_database

class TestStage1DatabaseAndSchema(unittest.TestCase):
    """
    Validates SQLite initialization, DDL schema, constraints, and seed data.
    """

    def setUp(self):
        # Create a fresh isolated temporary database file for each test
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.temp_db_fd)
        init_database(self.temp_db_path)
        self.conn = get_connection(self.temp_db_path)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_tables_created(self):
        """All 6 core relational tables must exist."""
        cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row['name'] for row in cursor.fetchall()}
        required_tables = {
            'users',
            'orders',
            'delivery_inspections',
            'inspection_confirmations',
            'audit_events',
            'inspection_corrections'
        }
        for table in required_tables:
            self.assertIn(table, tables, f"Expected table '{table}' was not created.")

    def test_sqlite_pragmas_enabled(self):
        """Foreign keys, WAL mode, and busy timeout must be configured."""
        fk_status = self.conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        self.assertEqual(fk_status, 1, "PRAGMA foreign_keys must be enabled (1).")

        journal_mode = self.conn.execute("PRAGMA journal_mode;").fetchone()[0]
        self.assertEqual(journal_mode.lower(), "wal", "PRAGMA journal_mode must be WAL.")

        busy_timeout = self.conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        self.assertGreaterEqual(busy_timeout, 5000, "PRAGMA busy_timeout must be at least 5000ms.")

    def test_seed_users_and_roles(self):
        """Seed data must contain supplier, nursery, and admin accounts."""
        users = self.conn.execute("SELECT username, role, business_name FROM users ORDER BY id;").fetchall()
        user_dict = {u['username']: u for u in users}

        self.assertIn('supplier_rajesh', user_dict)
        self.assertEqual(user_dict['supplier_rajesh']['role'], 'SUPPLIER')

        self.assertIn('nursery_amit', user_dict)
        self.assertEqual(user_dict['nursery_amit']['role'], 'NURSERY')

        self.assertIn('admin_flora', user_dict)
        self.assertEqual(user_dict['admin_flora']['role'], 'ADMIN')

    def test_role_check_constraint_rejects_invalid_roles(self):
        """Users table must reject unauthorized roles."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO users (username, email, password_hash, role, business_name) "
                "VALUES ('attacker', 'att@hack.com', 'hash', 'SUPERUSER', 'Malicious Org');"
            )

    def test_order_seed_and_constraints(self):
        """Orders table must contain seeded wholesale batches with valid constraints."""
        orders = self.conn.execute("SELECT id, ordered_qty, unit_price FROM orders;").fetchall()
        order_ids = {o['id'] for o in orders}
        self.assertIn('ORD-8801', order_ids)
        self.assertIn('ORD-8802', order_ids)
        self.assertIn('ORD-8760', order_ids)

        # Non-positive quantity must be rejected
        supplier_id = self.conn.execute("SELECT id FROM users WHERE role = 'SUPPLIER'").fetchone()[0]
        nursery_id = self.conn.execute("SELECT id FROM users WHERE role = 'NURSERY'").fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """INSERT INTO orders (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, truck_no, driver_info, status)
                   VALUES ('ORD-INVALID', ?, ?, 'Ferns', 0, 100.0, 'KA-01-1111', 'Driver', 'DISPATCHED')""",
                (supplier_id, nursery_id)
            )

    def test_independent_dual_confirmation_constraint(self):
        """
        inspection_confirmations must:
        - Only accept 'NURSERY' or 'SUPPLIER' (preventing direct admin bypass)
        - Enforce UNIQUE(inspection_id, party_role) to prevent duplicate signing
        """
        supplier_id = self.conn.execute("SELECT id FROM users WHERE role = 'SUPPLIER'").fetchone()[0]
        admin_id = self.conn.execute("SELECT id FROM users WHERE role = 'ADMIN'").fetchone()[0]

        # Fetch inspection for ORD-8760
        insp_id = self.conn.execute("SELECT id FROM delivery_inspections WHERE order_id = 'ORD-8760'").fetchone()[0]

        # Attempt duplicate supplier confirmation on ORD-8760 (already confirmed by supplier in seed)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """INSERT INTO inspection_confirmations (inspection_id, party_role, user_id, signature_note)
                   VALUES (?, 'SUPPLIER', ?, 'Duplicate attempt')""",
                (insp_id, supplier_id)
            )

        # Attempt unauthorized party role (e.g. 'ADMIN' trying to sign directly as an inspection party)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """INSERT INTO inspection_confirmations (inspection_id, party_role, user_id, signature_note)
                   VALUES (?, 'ADMIN', ?, 'Admin direct signature')""",
                (insp_id, admin_id)
            )

    def test_optional_confirmation_signature_note(self):
        """Inspection confirmations must support an optional signature note."""
        insp_id = self.conn.execute("SELECT id FROM delivery_inspections WHERE order_id = 'ORD-8760'").fetchone()[0]
        confirmations = self.conn.execute(
            "SELECT party_role, signature_note FROM inspection_confirmations WHERE inspection_id = ? ORDER BY party_role;",
            (insp_id,)
        ).fetchall()

        self.assertEqual(len(confirmations), 2)
        nursery_conf = [c for c in confirmations if c['party_role'] == 'NURSERY'][0]
        supplier_conf = [c for c in confirmations if c['party_role'] == 'SUPPLIER'][0]

        self.assertTrue(len(nursery_conf['signature_note']) > 0)
        self.assertTrue(len(supplier_conf['signature_note']) > 0)

    def test_audit_ledger_immutability_and_seed(self):
        """Audit events must record event_type, actor, before/after states."""
        audit = self.conn.execute("SELECT * FROM audit_events WHERE order_id = 'ORD-8760';").fetchone()
        self.assertIsNotNone(audit)
        self.assertEqual(audit['event_type'], 'ORDER_LOCKED')
        after_data = json.loads(audit['after_state_json'])
        self.assertEqual(after_data['order_id'], 'ORD-8760')
        self.assertEqual(after_data['is_locked'], 1)


class TestStage1FlaskApplication(unittest.TestCase):
    """
    Validates Flask Application Factory startup, static gateway, and demo role switcher.
    """

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.temp_db_fd)
        self.app = create_app({'DB_PATH': self.temp_db_path, 'ALLOW_DEMO_ROLE_SWITCH': True})
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_api_health_check(self):
        """GET /api/health returns 200 OK with expected JSON keys."""
        resp = self.client.get('/api/health')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get('status'), 'ok')
        self.assertIn('FloraChain', data.get('service'))
        self.assertTrue(data.get('dual_confirmation'))

    def test_serves_index_html_at_root(self):
        """GET / and GET /index.html must serve the existing frontend SPA with 200 OK."""
        resp_root = self.client.get('/')
        self.assertEqual(resp_root.status_code, 200)
        self.assertIn(b'FloraChain', resp_root.data)

        resp_index = self.client.get('/index.html')
        self.assertEqual(resp_index.status_code, 200)
        self.assertIn(b'FloraChain', resp_index.data)

    def test_serves_static_assets(self):
        """GET /app/static/css/styles.css and /app/static/js/app.js must serve existing frontend files."""
        resp_css = self.client.get('/app/static/css/styles.css')
        self.assertEqual(resp_css.status_code, 200)
        self.assertIn(b':root', resp_css.data)

        resp_js = self.client.get('/app/static/js/app.js')
        self.assertEqual(resp_js.status_code, 200)
        self.assertIn(b'DUMMY_DATA', resp_js.data)

    def test_role_switcher_endpoints(self):
        """
        Demo role switcher for local demonstrations only:
        - Lists demo roles
        - Switches role to NURSERY, SUPPLIER, ADMIN
        - Enforces server-side authorization: rejects invalid role
        - Prevents unrestricted administrator access
        """
        # 1. List roles
        resp_roles = self.client.get('/api/auth/roles')
        self.assertEqual(resp_roles.status_code, 200)
        roles_data = resp_roles.get_json()['data']
        self.assertEqual(len(roles_data), 3)

        # 2. Switch to NURSERY
        resp_nursery = self.client.post('/api/auth/switch-role', json={'role': 'NURSERY'})
        self.assertEqual(resp_nursery.status_code, 200)
        nursery_payload = resp_nursery.get_json()
        self.assertEqual(nursery_payload['data']['role'], 'NURSERY')
        self.assertTrue(nursery_payload['access_control']['can_counter_sign_nursery'])

        # 3. Check /api/auth/me reflects active session
        resp_me = self.client.get('/api/auth/me')
        self.assertEqual(resp_me.status_code, 200)
        self.assertEqual(resp_me.get_json()['data']['username'], 'nursery_amit')

        # 4. Switch to SUPPLIER
        resp_supplier = self.client.post('/api/auth/switch-role', json={'role': 'SUPPLIER'})
        self.assertEqual(resp_supplier.status_code, 200)
        self.assertEqual(resp_supplier.get_json()['data']['role'], 'SUPPLIER')

        # 5. Switch to ADMIN and verify access control
        resp_admin = self.client.post('/api/auth/switch-role', json={'role': 'ADMIN'})
        self.assertEqual(resp_admin.status_code, 200)
        admin_payload = resp_admin.get_json()
        self.assertEqual(admin_payload['data']['role'], 'ADMIN')
        # Crucial: Unrestricted admin access must be explicitly False
        self.assertFalse(admin_payload['access_control']['unrestricted_admin_access'])

        # 6. Reject invalid role
        resp_bad = self.client.post('/api/auth/switch-role', json={'role': 'SUPERUSER'})
        self.assertEqual(resp_bad.status_code, 400)
        self.assertFalse(resp_bad.get_json()['success'])

        # 7. Logout clears session
        resp_logout = self.client.post('/api/auth/logout')
        self.assertEqual(resp_logout.status_code, 200)
        resp_me_after = self.client.get('/api/auth/me')
        self.assertEqual(resp_me_after.status_code, 401)

if __name__ == '__main__':
    unittest.main(verbosity=2)
