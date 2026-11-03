"""
FloraChain B2B — Stage 2 Authentication & Authorization Test Suite
Tests:
1. Valid login using username and hashed password
2. Valid login using email address
3. Invalid password rejection (401)
4. Nonexistent user rejection (401)
5. Missing credentials validation (400)
6. Preventing role-only login without credentials (400)
7. Session persistence across requests and /api/auth/me inspection
8. Logout session clearance and subsequent 401 protection
9. Role-based access control (@require_role) for SUPPLIER, NURSERY, and ADMIN
10. Cross-role unauthorized access rejection (403)
11. Unauthenticated access rejection on protected routes (401)
12. Strict Party Confirmation Guardrails: Administrators CANNOT satisfy delivery confirmations
13. Demo role switcher disabled by default (403)
14. Demo role switcher enabled in explicit local-development mode
15. Demo role switcher rejects invalid roles even in development mode
"""

import unittest
import os
import sys
import tempfile
import json

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app

class TestStage2Authentication(unittest.TestCase):
    """
    Tests for credential validation, password hashing, session management, and logout.
    """

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.temp_db_fd)
        # Create app with default configuration (demo switcher disabled by default)
        self.app = create_app({'DB_PATH': self.temp_db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_login_valid_username_and_password(self):
        """Valid username + password returns 200, sets session cookie, and returns user profile."""
        resp = self.client.post('/api/auth/login', json={
            'username': 'supplier_rajesh',
            'password': 'password123'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['username'], 'supplier_rajesh')
        self.assertEqual(data['data']['role'], 'SUPPLIER')
        self.assertEqual(data['data']['business_name'], 'GreenRoots Wholesale Farms')
        self.assertNotIn('password_hash', data['data'])

    def test_login_valid_email_and_password(self):
        """Valid email + password returns 200 and authenticates user."""
        resp = self.client.post('/api/auth/login', json={
            'email': 'purchasing@greenmeadows.com',
            'password': 'password123'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['username'], 'nursery_amit')
        self.assertEqual(data['data']['role'], 'NURSERY')

    def test_login_invalid_password_rejected(self):
        """Invalid password must return 401 Unauthorized without setting session."""
        resp = self.client.post('/api/auth/login', json={
            'username': 'supplier_rajesh',
            'password': 'wrong_password_999'
        })
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Invalid', data['error'])

        # Verify no session was created
        resp_me = self.client.get('/api/auth/me')
        self.assertEqual(resp_me.status_code, 401)

    def test_login_nonexistent_user_rejected(self):
        """Nonexistent username or email must return 401 Unauthorized."""
        resp = self.client.post('/api/auth/login', json={
            'username': 'ghost_user',
            'password': 'password123'
        })
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.get_json()['success'])

    def test_login_missing_credentials(self):
        """Missing username or password must return 400 Bad Request."""
        # Empty body
        resp1 = self.client.post('/api/auth/login', json={})
        self.assertEqual(resp1.status_code, 400)

        # Missing password
        resp2 = self.client.post('/api/auth/login', json={'username': 'supplier_rajesh'})
        self.assertEqual(resp2.status_code, 400)

    def test_login_prevent_role_only_login(self):
        """User cannot gain a role merely by submitting a role name."""
        resp = self.client.post('/api/auth/login', json={'role': 'ADMIN'})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Cannot authenticate merely by role name', data['error'])

    def test_session_persistence_and_me_endpoint(self):
        """Authenticated session persists across requests and /api/auth/me reflects active session."""
        # Step 1: Login
        login_resp = self.client.post('/api/auth/login', json={
            'username': 'nursery_amit',
            'password': 'password123'
        })
        self.assertEqual(login_resp.status_code, 200)

        # Step 2: Query /me using the established session cookie
        me_resp = self.client.get('/api/auth/me')
        self.assertEqual(me_resp.status_code, 200)
        me_data = me_resp.get_json()
        self.assertTrue(me_data['authenticated'])
        self.assertEqual(me_data['data']['username'], 'nursery_amit')
        self.assertEqual(me_data['data']['role'], 'NURSERY')
        self.assertTrue(me_data['permissions']['can_counter_sign_nursery'])
        self.assertFalse(me_data['permissions']['can_counter_sign_supplier'])

    def test_logout_clears_session(self):
        """Logout invalidates the session; subsequent /api/auth/me queries return 401."""
        # Login
        self.client.post('/api/auth/login', json={
            'username': 'admin_flora',
            'password': 'password123'
        })

        # Verify active
        self.assertEqual(self.client.get('/api/auth/me').status_code, 200)

        # Logout
        logout_resp = self.client.post('/api/auth/logout')
        self.assertEqual(logout_resp.status_code, 200)

        # Verify cleared
        me_after = self.client.get('/api/auth/me')
        self.assertEqual(me_after.status_code, 401)


class TestStage2RoleBasedAccessControl(unittest.TestCase):
    """
    Tests for server-side role enforcement, cross-role prevention, and admin confirmation restrictions.
    """

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.temp_db_fd)
        self.app = create_app({'DB_PATH': self.temp_db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_unauthenticated_blocked_on_protected_routes(self):
        """Unauthenticated requests to protected areas must receive 401 Unauthorized."""
        self.assertEqual(self.client.get('/api/auth/supplier-area').status_code, 401)
        self.assertEqual(self.client.get('/api/auth/nursery-area').status_code, 401)
        self.assertEqual(self.client.get('/api/auth/admin-area').status_code, 401)

    def test_supplier_role_access_and_boundaries(self):
        """SUPPLIER can access supplier area, but is rejected (403) from nursery and admin areas."""
        self.client.post('/api/auth/login', json={'username': 'supplier_rajesh', 'password': 'password123'})

        # Allowed
        resp_supp = self.client.get('/api/auth/supplier-area')
        self.assertEqual(resp_supp.status_code, 200)
        self.assertIn('supplier_rajesh', resp_supp.get_json()['message'])

        # Forbidden on nursery
        resp_nurs = self.client.get('/api/auth/nursery-area')
        self.assertEqual(resp_nurs.status_code, 403)

        # Forbidden on admin
        resp_admin = self.client.get('/api/auth/admin-area')
        self.assertEqual(resp_admin.status_code, 403)

    def test_nursery_role_access_and_boundaries(self):
        """NURSERY can access nursery area, but is rejected (403) from supplier and admin areas."""
        self.client.post('/api/auth/login', json={'username': 'nursery_amit', 'password': 'password123'})

        # Allowed
        resp_nurs = self.client.get('/api/auth/nursery-area')
        self.assertEqual(resp_nurs.status_code, 200)

        # Forbidden on supplier
        resp_supp = self.client.get('/api/auth/supplier-area')
        self.assertEqual(resp_supp.status_code, 403)

        # Forbidden on admin
        resp_admin = self.client.get('/api/auth/admin-area')
        self.assertEqual(resp_admin.status_code, 403)

    def test_admin_role_access_and_boundaries(self):
        """ADMIN can access admin area, but is rejected (403) from party-specific operational areas."""
        self.client.post('/api/auth/login', json={'username': 'admin_flora', 'password': 'password123'})

        # Allowed on admin
        resp_admin = self.client.get('/api/auth/admin-area')
        self.assertEqual(resp_admin.status_code, 200)

        # Forbidden on supplier operational area
        self.assertEqual(self.client.get('/api/auth/supplier-area').status_code, 403)

        # Forbidden on nursery operational area
        self.assertEqual(self.client.get('/api/auth/nursery-area').status_code, 403)

    def test_admin_cannot_impersonate_or_satisfy_delivery_confirmations(self):
        """
        Requirement 5: Administrators cannot impersonate either party or satisfy
        either of the two independent delivery confirmations.
        """
        self.client.post('/api/auth/login', json={'username': 'admin_flora', 'password': 'password123'})

        # 1. Admin attempts to satisfy nursery delivery confirmation
        resp_nurs = self.client.post('/api/auth/check-confirmation-permission', json={'party_role': 'NURSERY'})
        self.assertEqual(resp_nurs.status_code, 403)
        self.assertFalse(resp_nurs.get_json()['allowed'])
        self.assertIn('Administrators cannot impersonate either party', resp_nurs.get_json()['error'])

        # 2. Admin attempts to satisfy supplier delivery confirmation
        resp_supp = self.client.post('/api/auth/check-confirmation-permission', json={'party_role': 'SUPPLIER'})
        self.assertEqual(resp_supp.status_code, 403)
        self.assertFalse(resp_supp.get_json()['allowed'])
        self.assertIn('Administrators cannot impersonate either party', resp_supp.get_json()['error'])

    def test_party_users_can_only_confirm_their_own_role(self):
        """Supplier can only confirm as SUPPLIER; Nursery can only confirm as NURSERY."""
        # As Supplier
        self.client.post('/api/auth/login', json={'username': 'supplier_rajesh', 'password': 'password123'})
        resp_ok = self.client.post('/api/auth/check-confirmation-permission', json={'party_role': 'SUPPLIER'})
        self.assertEqual(resp_ok.status_code, 200)
        self.assertTrue(resp_ok.get_json()['allowed'])

        resp_forbidden = self.client.post('/api/auth/check-confirmation-permission', json={'party_role': 'NURSERY'})
        self.assertEqual(resp_forbidden.status_code, 403)
        self.assertFalse(resp_forbidden.get_json()['allowed'])


class TestStage2DemoModeRestrictions(unittest.TestCase):
    """
    Tests for demonstration role switcher restrictions:
    - Disabled by default outside local-development mode
    - Enabled only when explicitly configured
    - Validates server-side authorization even when enabled
    """

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.temp_db_fd)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_demo_switcher_disabled_by_default(self):
        """When ALLOW_DEMO_ROLE_SWITCH is False (default), demo endpoints return 403 Forbidden."""
        app = create_app({'DB_PATH': self.temp_db_path, 'ALLOW_DEMO_ROLE_SWITCH': False})
        client = app.test_client()

        # Listing roles returns 403
        resp_roles = client.get('/api/auth/roles')
        self.assertEqual(resp_roles.status_code, 403)
        self.assertIn('Demonstration mode is disabled', resp_roles.get_json()['error'])

        # Switching role returns 403
        resp_switch = client.post('/api/auth/switch-role', json={'role': 'NURSERY'})
        self.assertEqual(resp_switch.status_code, 403)
        self.assertIn('Demonstration role switcher is disabled', resp_switch.get_json()['error'])

    def test_demo_switcher_when_explicitly_enabled(self):
        """When ALLOW_DEMO_ROLE_SWITCH is explicitly True, demo switcher functions for permitted roles."""
        app = create_app({'DB_PATH': self.temp_db_path, 'ALLOW_DEMO_ROLE_SWITCH': True})
        client = app.test_client()

        # Listing roles returns 200
        resp_roles = client.get('/api/auth/roles')
        self.assertEqual(resp_roles.status_code, 200)
        self.assertEqual(len(resp_roles.get_json()['data']), 3)

        # Switching role to NURSERY works
        resp_nurs = client.post('/api/auth/switch-role', json={'role': 'NURSERY'})
        self.assertEqual(resp_nurs.status_code, 200)
        self.assertEqual(resp_nurs.get_json()['data']['username'], 'nursery_amit')

        # /me reflects the switched role
        resp_me = client.get('/api/auth/me')
        self.assertEqual(resp_me.status_code, 200)
        self.assertEqual(resp_me.get_json()['data']['role'], 'NURSERY')

        # Invalid demo role is still rejected with 400
        resp_bad = client.post('/api/auth/switch-role', json={'role': 'SUPERUSER'})
        self.assertEqual(resp_bad.status_code, 400)
        self.assertIn('Invalid role', resp_bad.get_json()['error'])

        # Admin switched session still has unrestricted_admin_access = False
        resp_admin = client.post('/api/auth/switch-role', json={'role': 'ADMIN'})
        self.assertEqual(resp_admin.status_code, 200)
        self.assertFalse(resp_admin.get_json()['access_control']['unrestricted_admin_access'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
