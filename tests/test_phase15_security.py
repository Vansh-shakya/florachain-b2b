"""
FloraChain B2B — Phase 15 Security Remediation Test Suite
Tests:
1. CSRF Protection:
   - CSRF token acquisition (/api/auth/csrf-token, /api/auth/me, cookie, and login response)
   - Mutating request rejection when CSRF token is missing (403)
   - Mutating request rejection when CSRF token is invalid (403)
   - Mutating request acceptance with valid X-CSRF-Token header
   - Mutating request acceptance with valid csrf_token JSON body
   - Safe GET requests exemption
   - Login endpoint exemption
2. Object-Level Authorization on Order History:
   - GET /api/orders/<order_id>/confirmations and GET /api/orders/<order_id>/audit
   - 401 for unauthenticated requests
   - 404 for nonexistent order IDs
   - 403 for unrelated suppliers and nurseries
   - 200 for authorized supplier, authorized nursery, and platform admin
3. Session Cookie Security & Expiration:
   - SESSION_COOKIE_SECURE = True in ProductionConfig, False in DevelopmentConfig
   - PERMANENT_SESSION_LIFETIME = 8 hours
   - session.permanent set to True on authentication
4. Admin Authentication Status Codes:
   - 401 Unauthorized for unauthenticated requests to /api/admin/corrections
   - 403 Forbidden for authenticated non-admin users
   - 200 OK for authenticated admin
"""

import unittest
import os
import sys
import json
import tempfile
from datetime import timedelta

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.config import (
    Config,
    DevelopmentConfig,
    TestingConfig,
    ProductionConfig,
    get_config
)
from app.models.database import get_connection, init_database


class TestPhase15SecurityRemediation(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        self.app = create_app({
            'TESTING': True,
            'DB_PATH': self.temp_db_path,
            'SECRET_KEY': 'phase15-security-verified-secret',
            'ALLOW_DEMO_ROLE_SWITCH': True,
            'CSRF_ENABLED': True
        })
        self.client = self.app.test_client()

        # Initialize schema and seed data
        init_database(self.temp_db_path)

        # Retrieve test users
        conn = get_connection(self.temp_db_path)
        try:
            # We also create a secondary supplier and secondary nursery for IDOR tests
            with conn:
                conn.execute(
                    """INSERT INTO users (id, username, email, password_hash, role, business_name)
                       VALUES (101, 'supplier_unrelated', 'unrelated_supp@florachain.test', 
                               'scrypt:32768:8:1$mock$hash', 'SUPPLIER', 'Unrelated Wholesale Nursery')"""
                )
                conn.execute(
                    """INSERT INTO users (id, username, email, password_hash, role, business_name)
                       VALUES (102, 'nursery_unrelated', 'unrelated_nurs@florachain.test', 
                               'scrypt:32768:8:1$mock$hash', 'NURSERY', 'Unrelated Retail Garden')"""
                )

            self.supplier = dict(conn.execute("SELECT * FROM users WHERE username = 'supplier_rajesh'").fetchone())
            self.nursery = dict(conn.execute("SELECT * FROM users WHERE username = 'nursery_amit'").fetchone())
            self.admin = dict(conn.execute("SELECT * FROM users WHERE username = 'admin_flora'").fetchone())
            self.unrelated_supp = dict(conn.execute("SELECT * FROM users WHERE username = 'supplier_unrelated'").fetchone())
            self.unrelated_nurs = dict(conn.execute("SELECT * FROM users WHERE username = 'nursery_unrelated'").fetchone())
        finally:
            conn.close()

    def tearDown(self):
        try:
            os.close(self.temp_db_fd)
            if os.path.exists(self.temp_db_path):
                os.unlink(self.temp_db_path)
        except OSError:
            pass

    # =========================================================================
    # 1. CSRF PROTECTION TESTS
    # =========================================================================

    def test_01_csrf_token_endpoint(self):
        """GET /api/auth/csrf-token returns token and sets cookie."""
        res = self.client.get('/api/auth/csrf-token')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(len(data['csrf_token']) >= 32)

        # Check response header and cookie
        self.assertEqual(res.headers.get('X-CSRF-Token'), data['csrf_token'])
        cookie_header = res.headers.get('Set-Cookie', '')
        self.assertIn('csrf_token=', cookie_header)

    def test_02_login_exempt_from_csrf_and_issues_token(self):
        """POST /api/auth/login does not require CSRF and returns fresh token."""
        res = self.client.post('/api/auth/login', json={
            'username': 'supplier_rajesh',
            'password': 'password123'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('csrf_token', data)
        self.assertIn('csrf_token', data['data'])

    def test_03_mutating_request_rejected_without_csrf_token(self):
        """Authenticated state-changing request without CSRF token returns 403."""
        # Login
        self.client.post('/api/auth/login', json={
            'username': 'supplier_rajesh',
            'password': 'password123'
        })

        # Attempt mutating action without X-CSRF-Token
        payload = {
            'common_name': 'New Test Palm',
            'botanical_name': 'Palma testus',
            'category': 'Palms',
            'container_size': '10-inch',
            'unit_price': 150.0,
            'stock_quantity': 50
        }
        res = self.client.post('/api/plants', json=payload)
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('CSRF token missing or invalid', data['error'])

    def test_04_mutating_request_rejected_with_invalid_csrf_token(self):
        """Authenticated state-changing request with invalid CSRF token returns 403."""
        self.client.post('/api/auth/login', json={
            'username': 'supplier_rajesh',
            'password': 'password123'
        })

        res = self.client.post(
            '/api/plants',
            json={'common_name': 'Bogus Plant'},
            headers={'X-CSRF-Token': 'invalid-forged-token-12345'}
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('CSRF token missing or invalid', data['error'])

    def test_05_mutating_request_accepted_with_valid_header_csrf_token(self):
        """Authenticated state-changing request with valid X-CSRF-Token header succeeds."""
        login_res = self.client.post('/api/auth/login', json={
            'username': 'supplier_rajesh',
            'password': 'password123'
        })
        token = login_res.get_json()['csrf_token']

        payload = {
            'common_name': 'Verified Security Palm',
            'botanical_name': 'Palma securitas',
            'category': 'PALM',
            'container_size': '10-inch Pot',
            'unit': 'pot',
            'unit_price': 175.0,
            'stock_qty': 40,
            'min_order_qty': 5,
            'status': 'ACTIVE'
        }
        res = self.client.post(
            '/api/plants',
            json=payload,
            headers={'X-CSRF-Token': token}
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])

    def test_06_mutating_request_accepted_with_valid_body_csrf_token(self):
        """Authenticated state-changing request with valid csrf_token in JSON body succeeds."""
        login_res = self.client.post('/api/auth/login', json={
            'username': 'supplier_rajesh',
            'password': 'password123'
        })
        token = login_res.get_json()['csrf_token']

        payload = {
            'csrf_token': token,
            'common_name': 'Body Token Shrub',
            'botanical_name': 'Frutex securitas',
            'category': 'ORNAMENTAL',
            'container_size': '8-inch Pot',
            'unit': 'pot',
            'unit_price': 120.0,
            'stock_qty': 30,
            'min_order_qty': 5,
            'status': 'ACTIVE'
        }
        res = self.client.post('/api/plants', json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])

    def test_07_safe_get_requests_exempt_from_csrf(self):
        """GET requests do not require a CSRF token."""
        self.client.post('/api/auth/login', json={
            'username': 'supplier_rajesh',
            'password': 'password123'
        })
        res = self.client.get('/api/plants')
        self.assertEqual(res.status_code, 200)

    # =========================================================================
    # 2. OBJECT-LEVEL AUTHORIZATION ON ORDER HISTORY TESTS
    # =========================================================================

    def test_08_order_confirmations_unauthenticated_returns_401(self):
        """Unauthenticated request to order confirmations returns 401."""
        res = self.client.get('/api/orders/ORD-8801/confirmations')
        self.assertEqual(res.status_code, 401)

    def test_09_order_audit_unauthenticated_returns_401(self):
        """Unauthenticated request to order audit trail returns 401."""
        res = self.client.get('/api/orders/ORD-8801/audit')
        self.assertEqual(res.status_code, 401)

    def test_10_order_confirmations_nonexistent_order_returns_404(self):
        """Request for nonexistent order confirmations returns 404."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.supplier['id']
            sess['role'] = 'SUPPLIER'
            sess['username'] = self.supplier['username']

        res = self.client.get('/api/orders/ORD-NONEXISTENT-9999/confirmations')
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('not found', data['error'].lower())

    def test_11_order_audit_nonexistent_order_returns_404(self):
        """Request for nonexistent order audit trail returns 404."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.supplier['id']
            sess['role'] = 'SUPPLIER'
            sess['username'] = self.supplier['username']

        res = self.client.get('/api/orders/ORD-NONEXISTENT-9999/audit')
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('not found', data['error'].lower())

    def test_12_order_confirmations_unrelated_parties_returns_403(self):
        """Unrelated supplier and unrelated nursery are denied access to order confirmations."""
        # Unrelated supplier
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.unrelated_supp['id']
            sess['role'] = 'SUPPLIER'
            sess['username'] = self.unrelated_supp['username']

        res_supp = self.client.get('/api/orders/ORD-8801/confirmations')
        self.assertEqual(res_supp.status_code, 403)
        self.assertIn('Unauthorized', res_supp.get_json()['error'])

        # Unrelated nursery
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.unrelated_nurs['id']
            sess['role'] = 'NURSERY'
            sess['username'] = self.unrelated_nurs['username']

        res_nurs = self.client.get('/api/orders/ORD-8801/confirmations')
        self.assertEqual(res_nurs.status_code, 403)
        self.assertIn('Unauthorized', res_nurs.get_json()['error'])

    def test_13_order_audit_unrelated_parties_returns_403(self):
        """Unrelated supplier and unrelated nursery are denied access to order audit trail."""
        # Unrelated supplier
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.unrelated_supp['id']
            sess['role'] = 'SUPPLIER'
            sess['username'] = self.unrelated_supp['username']

        res_supp = self.client.get('/api/orders/ORD-8801/audit')
        self.assertEqual(res_supp.status_code, 403)
        self.assertIn('Unauthorized', res_supp.get_json()['error'])

        # Unrelated nursery
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.unrelated_nurs['id']
            sess['role'] = 'NURSERY'
            sess['username'] = self.unrelated_nurs['username']

        res_nurs = self.client.get('/api/orders/ORD-8801/audit')
        self.assertEqual(res_nurs.status_code, 403)
        self.assertIn('Unauthorized', res_nurs.get_json()['error'])

    def test_14_order_confirmations_and_audit_authorized_parties_allowed(self):
        """Assigned supplier, assigned nursery, and admin can access confirmations and audit trail."""
        for user in [self.supplier, self.nursery, self.admin]:
            with self.client.session_transaction() as sess:
                sess['user_id'] = user['id']
                sess['role'] = user['role']
                sess['username'] = user['username']

            res_conf = self.client.get('/api/orders/ORD-8801/confirmations')
            self.assertEqual(res_conf.status_code, 200, f"Failed for {user['username']}")
            self.assertTrue(res_conf.get_json()['success'])

            res_audit = self.client.get('/api/orders/ORD-8801/audit')
            self.assertEqual(res_audit.status_code, 200, f"Failed for {user['username']}")
            self.assertTrue(res_audit.get_json()['success'])

    # =========================================================================
    # 3. SESSION COOKIE SECURITY & EXPIRATION TESTS
    # =========================================================================

    def test_15_production_config_enforces_secure_cookie(self):
        """ProductionConfig must set SESSION_COOKIE_SECURE to True."""
        self.assertTrue(ProductionConfig.SESSION_COOKIE_SECURE)
        self.assertFalse(DevelopmentConfig.SESSION_COOKIE_SECURE)

    def test_16_permanent_session_lifetime_and_permanence(self):
        """PERMANENT_SESSION_LIFETIME is 8 hours and session.permanent is set on login."""
        self.assertEqual(Config.PERMANENT_SESSION_LIFETIME, timedelta(hours=8))
        self.assertEqual(self.app.config['PERMANENT_SESSION_LIFETIME'], timedelta(hours=8))

        # Perform login and check that session is permanent
        with self.client:
            self.client.post('/api/auth/login', json={
                'username': 'supplier_rajesh',
                'password': 'password123'
            })
            from flask import session as flask_session
            self.assertTrue(flask_session.permanent)

    # =========================================================================
    # 4. ADMIN AUTHENTICATION STATUS CODES
    # =========================================================================

    def test_17_admin_corrections_unauthenticated_returns_401(self):
        """Unauthenticated request to /api/admin/corrections returns 401."""
        res = self.client.get('/api/admin/corrections')
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Authentication required', data['error'])

    def test_18_admin_corrections_non_admin_returns_403(self):
        """Authenticated non-admin request to /api/admin/corrections returns 403."""
        for user in [self.supplier, self.nursery]:
            with self.client.session_transaction() as sess:
                sess['user_id'] = user['id']
                sess['role'] = user['role']
                sess['username'] = user['username']

            res = self.client.get('/api/admin/corrections')
            self.assertEqual(res.status_code, 403, f"Failed for {user['username']}")
            data = res.get_json()
            self.assertFalse(data['success'])
            self.assertIn('Administrator privileges required', data['error'])

    def test_19_admin_corrections_admin_allowed_returns_200(self):
        """Authenticated admin request to /api/admin/corrections returns 200."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin['id']
            sess['role'] = self.admin['role']
            sess['username'] = self.admin['username']

        res = self.client.get('/api/admin/corrections')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('data', data)


if __name__ == '__main__':
    unittest.main()
