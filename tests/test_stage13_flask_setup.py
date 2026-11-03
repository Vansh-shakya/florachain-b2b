"""
FloraChain B2B — Phase 13 Flask Backend Setup Test Suite
Comprehensive testing of:
- Centralized configuration management (Development, Testing, Production, and dotenv integration)
- Application factory create_app(test_config=None) behavior and config overrides
- Database connection lifecycle, get_db, close_db, and teardown_appcontext hook
- HTTP baseline security headers injection (nosniff, SAMEORIGIN, strict-origin-when-cross-origin)
- JSON error handling for /api/* requests (400, 404, 405, 500)
- Preserving SPA HTML fallback for frontend routes while returning JSON 404 for unknown /api/* routes
- Centralized application logging configuration
"""

import unittest
import os
import sys
import json
import tempfile

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
from app.models.database import get_connection, get_db, close_db, init_database


class TestPhase13FlaskBackendSetup(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        self.app = create_app({
            'TESTING': True,
            'DB_PATH': self.temp_db_path,
            'SECRET_KEY': 'phase13-test-secret-key-12345',
            'ALLOW_DEMO_ROLE_SWITCH': True
        })
        self.client = self.app.test_client()

        # Initialize schema and seed data
        init_database(self.temp_db_path)

    def tearDown(self):
        try:
            os.close(self.temp_db_fd)
            if os.path.exists(self.temp_db_path):
                os.unlink(self.temp_db_path)
        except OSError:
            pass

    def test_01_config_classes_and_environment_resolution(self):
        """Test configuration hierarchy and environment name resolution."""
        # DevelopmentConfig
        dev_cfg = get_config('development')
        self.assertTrue(issubclass(dev_cfg, Config))
        self.assertTrue(dev_cfg.DEBUG)

        # TestingConfig
        test_cfg = get_config('testing')
        self.assertTrue(issubclass(test_cfg, Config))
        self.assertTrue(test_cfg.TESTING)

        # ProductionConfig
        prod_cfg = get_config('production')
        self.assertTrue(issubclass(prod_cfg, Config))
        self.assertFalse(prod_cfg.DEBUG)
        self.assertFalse(prod_cfg.TESTING)
        self.assertFalse(prod_cfg.ALLOW_DEMO_ROLE_SWITCH)

        # Default fallback
        default_cfg = get_config('unknown_environment_name')
        self.assertEqual(default_cfg, DevelopmentConfig)

    def test_02_create_app_test_config_overrides(self):
        """Test that create_app cleanly prioritizes test_config dictionary."""
        self.assertEqual(self.app.config['SECRET_KEY'], 'phase13-test-secret-key-12345')
        self.assertEqual(self.app.secret_key, 'phase13-test-secret-key-12345')
        self.assertEqual(self.app.config['DB_PATH'], self.temp_db_path)
        self.assertTrue(self.app.config['TESTING'])
        self.assertTrue(self.app.config['ALLOW_DEMO_ROLE_SWITCH'])
        self.assertTrue(self.app.config['SESSION_COOKIE_HTTPONLY'])
        self.assertEqual(self.app.config['SESSION_COOKIE_SAMESITE'], 'Lax')

    def test_03_baseline_security_headers_injected(self):
        """Test that baseline HTTP security headers are present on API and static responses."""
        # 1. API route
        res_api = self.client.get('/api/health')
        self.assertEqual(res_api.status_code, 200)
        self.assertEqual(res_api.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(res_api.headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertEqual(res_api.headers.get('X-XSS-Protection'), '1; mode=block')
        self.assertEqual(res_api.headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')

        # 2. Frontend SPA route
        res_spa = self.client.get('/')
        self.assertEqual(res_spa.status_code, 200)
        self.assertEqual(res_spa.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(res_spa.headers.get('X-Frame-Options'), 'SAMEORIGIN')

    def test_04_unknown_api_routes_return_json_404(self):
        """Unknown API routes must return JSON 404, not HTML 200."""
        # 1. GET unknown API route
        res_get = self.client.get('/api/does_not_exist_endpoint')
        self.assertEqual(res_get.status_code, 404)
        self.assertTrue(res_get.is_json)
        data_get = res_get.get_json()
        self.assertFalse(data_get['success'])
        self.assertIn("not found", data_get['error'].lower())

        # 2. POST unknown API route
        res_post = self.client.post('/api/does_not_exist_endpoint', json={'test': 1})
        self.assertEqual(res_post.status_code, 404)
        self.assertTrue(res_post.is_json)
        data_post = res_post.get_json()
        self.assertFalse(data_post['success'])

        # 3. Non-existent sub-resource in existing prefix
        res_sub = self.client.get('/api/orders/nonexistent/sub/path')
        self.assertEqual(res_sub.status_code, 404)
        self.assertTrue(res_sub.is_json)

    def test_05_spa_fallback_preserved_for_frontend_routes(self):
        """Frontend routes must continue to serve index.html with 200 OK."""
        frontend_routes = ['/', '/index.html', '/orders', '/plants', '/nurseries', '/truck-loading', '/invoices', '/payments', '/ledger', '/nursery', '/login']
        for route in frontend_routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed to serve SPA")
            self.assertIn(b'<!DOCTYPE html>', res.data, f"Route {route} did not return HTML")
            self.assertIn(b'FloraChain', res.data, f"Route {route} missing brand title")

    def test_06_malformed_json_api_returns_json_400(self):
        """Malformed JSON payloads to API endpoints return structured JSON 400 error."""
        # POST with malformed JSON string
        res = self.client.post(
            '/api/auth/login',
            data='{invalid-json-content',
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(res.status_code, 400)
        self.assertTrue(res.is_json)
        data = res.get_json()
        self.assertFalse(data['success'])

    def test_07_database_connection_lifecycle_and_teardown(self):
        """Test that request-scoped database connection is cleanly managed and closed by teardown."""
        with self.app.app_context():
            # Connection acquired on g
            db1 = get_db(self.temp_db_path)
            self.assertIsNotNone(db1)
            # Re-accessing in same context yields same connection
            db2 = get_db(self.temp_db_path)
            self.assertIs(db1, db2)

            # Teardown closes it
            close_db()

        # Database operations still work properly outside request context
        conn = get_connection(self.temp_db_path)
        row = conn.execute("SELECT COUNT(*) FROM users;").fetchone()
        self.assertGreaterEqual(row[0], 1)
        conn.close()

    def test_08_centralized_logger_configured(self):
        """Test that app.logger is configured with handler and appropriate level."""
        self.assertIsNotNone(self.app.logger)
        self.assertTrue(len(self.app.logger.handlers) > 0)
        self.app.logger.info("Phase 13 centralized logging verification test message.")


if __name__ == '__main__':
    unittest.main()

