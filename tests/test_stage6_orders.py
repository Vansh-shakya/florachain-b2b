"""
FloraChain B2B — Stage 6: Wholesale Order Management Tests
Validates Phase 6 multi-variety orders, itemized lines, calculations, security boundaries, and schema integrity.
"""

import os
import sys
import tempfile
import unittest
import sqlite3
from werkzeug.security import generate_password_hash

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models.database import get_connection, init_database


class TestStage6OrderManagement(unittest.TestCase):
    """
    Validates end-to-end database-backed wholesale order management,
    itemized line totals, mathematical validation, role-based isolation, and audit logging.
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

    def _login(self, client, username, password='password123'):
        resp = client.post('/api/auth/login', json={'username': username, 'password': password})
        self.assertEqual(resp.status_code, 200)
        return resp

    # =========================================================================
    # 1. SCHEMA & CONSTRAINT INTEGRITY TESTS
    # =========================================================================

    def test_schema_orders_allows_confirmed_and_expanded_statuses(self):
        """Orders table must accept CONFIRMED, STAGING, and other Phase 6 statuses."""
        conn = get_connection(self.temp_db_path)
        supp_id = conn.execute("SELECT id FROM users WHERE role = 'SUPPLIER'").fetchone()[0]
        nurs_id = conn.execute("SELECT id FROM users WHERE role = 'NURSERY'").fetchone()[0]

        # Inserting CONFIRMED order must succeed
        with conn:
            conn.execute(
                """INSERT INTO orders (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, status)
                   VALUES ('ORD-TEST-01', ?, ?, 'Test Variety', 50, 200.0, 'CONFIRMED')""",
                (supp_id, nurs_id)
            )

        row = conn.execute("SELECT status, truck_no, driver_info FROM orders WHERE id = 'ORD-TEST-01'").fetchone()
        self.assertEqual(row['status'], 'CONFIRMED')
        self.assertEqual(row['truck_no'], 'TBD')
        self.assertEqual(row['driver_info'], 'TBD')

        # Invalid status must raise IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """INSERT INTO orders (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, status)
                       VALUES ('ORD-TEST-INV', ?, ?, 'Test Variety', 50, 200.0, 'INVALID_STATUS')""",
                    (supp_id, nurs_id)
                )
        conn.close()

    def test_schema_order_items_constraints(self):
        """Order items table must strictly enforce positive quantity, price, and line_total."""
        conn = get_connection(self.temp_db_path)

        # Zero or negative quantity must fail
        with self.assertRaises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """INSERT INTO order_items (order_id, plant_id, variety, quantity, unit_price, line_total)
                       VALUES ('ORD-8801', 1, 'Areca Palm', 0, 350.0, 0.0)"""
                )

        # Negative price must fail
        with self.assertRaises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """INSERT INTO order_items (order_id, plant_id, variety, quantity, unit_price, line_total)
                       VALUES ('ORD-8801', 1, 'Areca Palm', 10, -50.0, -500.0)"""
                )
        conn.close()

    def test_seed_demo_orders_have_order_items(self):
        """All 3 initial demo orders must have corresponding order_items populated."""
        conn = get_connection(self.temp_db_path)
        items = conn.execute("SELECT order_id, variety, quantity, unit_price, line_total FROM order_items").fetchall()
        order_ids = {it['order_id'] for it in items}

        self.assertIn('ORD-8801', order_ids)
        self.assertIn('ORD-8802', order_ids)
        self.assertIn('ORD-8760', order_ids)

        # Check line total calculation for ORD-8801: 150 * 350 = 52500
        ord_8801_item = next(it for it in items if it['order_id'] == 'ORD-8801')
        self.assertEqual(ord_8801_item['quantity'], 150)
        self.assertEqual(ord_8801_item['unit_price'], 350.0)
        self.assertEqual(ord_8801_item['line_total'], 52500.0)

        # Zero foreign key violations
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(len(fk_errors), 0)
        conn.close()

    # =========================================================================
    # 2. AUTHENTICATION & ACCESS CONTROL TESTS
    # =========================================================================

    def test_unauthenticated_requests_rejected(self):
        """Unauthenticated requests to order endpoints must return 401."""
        self.assertEqual(self.client.get('/api/orders').status_code, 401)
        self.assertEqual(self.client.post('/api/orders', json={}).status_code, 401)
        self.assertEqual(self.client.get('/api/orders/ORD-8801').status_code, 401)
        self.assertEqual(self.client.get('/api/orders/nurseries').status_code, 401)

    def test_role_isolation_supplier_vs_nursery(self):
        """Suppliers see their orders, nurseries see orders assigned to them."""
        # Insert another supplier with an order
        conn = get_connection(self.temp_db_path)
        with conn:
            conn.execute(
                """INSERT INTO users (username, email, password_hash, role, business_name)
                   VALUES ('supplier_other', 'other@supplier.com', ?, 'SUPPLIER', 'Other Supplier Ltd')""",
                (generate_password_hash('password123'),)
            )
            other_supp_id = conn.execute("SELECT id FROM users WHERE username = 'supplier_other'").fetchone()[0]
            nurs_id = conn.execute("SELECT id FROM users WHERE username = 'nursery_amit'").fetchone()[0]

            conn.execute(
                """INSERT INTO orders (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, status)
                   VALUES ('ORD-OTHER-01', ?, ?, 'Exclusive Rose', 40, 500.0, 'CONFIRMED')""",
                (other_supp_id, nurs_id)
            )
        conn.close()

        # Login as supplier_rajesh: should NOT see ORD-OTHER-01
        self._login(self.client, 'supplier_rajesh')
        resp = self.client.get('/api/orders')
        self.assertEqual(resp.status_code, 200)
        rajesh_orders = resp.get_json()['data']
        rajesh_ids = [o['id'] for o in rajesh_orders]
        self.assertNotIn('ORD-OTHER-01', rajesh_ids)
        self.assertIn('ORD-8801', rajesh_ids)

        # Login as supplier_other: should ONLY see ORD-OTHER-01
        self.client.post('/api/auth/logout')
        self._login(self.client, 'supplier_other')
        resp = self.client.get('/api/orders')
        other_orders = resp.get_json()['data']
        other_ids = [o['id'] for o in other_orders]
        self.assertIn('ORD-OTHER-01', other_ids)
        self.assertNotIn('ORD-8801', other_ids)

        # Login as admin_flora: sees ALL orders
        self.client.post('/api/auth/logout')
        self._login(self.client, 'admin_flora')
        resp = self.client.get('/api/orders')
        admin_orders = resp.get_json()['data']
        admin_ids = [o['id'] for o in admin_orders]
        self.assertIn('ORD-8801', admin_ids)
        self.assertIn('ORD-OTHER-01', admin_ids)

    def test_nursery_role_cannot_create_order(self):
        """Only SUPPLIER or ADMIN can create wholesale orders; NURSERY is rejected with 403."""
        self._login(self.client, 'nursery_amit')
        resp = self.client.post('/api/orders', json={
            "nursery_user_id": 2,
            "items": [{"plant_id": 1, "variety": "Areca Palm", "quantity": 20, "unit_price": 350.0}]
        })
        self.assertEqual(resp.status_code, 403)
        self.assertIn("wholesale suppliers", resp.get_json()['error'])

    # =========================================================================
    # 3. ORDER CREATION & CALCULATION TESTS
    # =========================================================================

    def test_create_order_single_item_success(self):
        """Supplier creates a valid order with a single plant line item."""
        self._login(self.client, 'supplier_rajesh')

        # Nursery Amit is user_id 2
        payload = {
            "nursery_user_id": 2,
            "notes": "Urgent stock replenishment for weekend exhibition.",
            "items": [
                {
                    "plant_id": 1, # Areca Palm, price 350.0
                    "quantity": 25,
                    "unit_price": 350.0
                }
            ]
        }

        resp = self.client.post('/api/orders', json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])

        order_data = data['data']
        order_header = order_data['order']
        self.assertEqual(order_header['status'], 'CONFIRMED')
        self.assertEqual(order_header['ordered_qty'], 25)
        self.assertEqual(order_header['unit_price'], 350.0)
        self.assertEqual(order_data['total_amount'], 8750.0) # 25 * 350 = 8750
        self.assertEqual(len(order_data['items']), 1)
        self.assertEqual(order_data['items'][0]['line_total'], 8750.0)

    def test_create_order_multi_variety_calculation(self):
        """Supplier creates an order with multiple plant varieties; verifies line totals, grand total, and weighted average unit price."""
        self._login(self.client, 'supplier_rajesh')

        # 3 varieties:
        # Item 1: 30 x 350.0 = 10,500.0
        # Item 2: 50 x 180.0 = 9,000.0
        # Item 3: 20 x 420.0 = 8,400.0
        # Total Qty = 100
        # Total Value = 27,900.0
        # Weighted Average Unit Price = 279.0
        payload = {
            "nursery_user_id": 2,
            "notes": "Multi-variety landscape order",
            "items": [
                {"plant_id": 1, "variety": "Areca Palm", "quantity": 30, "unit_price": 350.0},
                {"plant_id": 2, "variety": "Bougainvillea Dwarf", "quantity": 50, "unit_price": 180.0},
                {"plant_id": 5, "variety": "Golden Pothos Totem", "quantity": 20, "unit_price": 420.0}
            ]
        }

        resp = self.client.post('/api/orders', json=payload)
        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()['data']

        order_header = body['order']
        self.assertEqual(order_header['ordered_qty'], 100)
        self.assertEqual(order_header['unit_price'], 279.0)
        self.assertEqual(body['total_amount'], 27900.0)
        self.assertEqual(len(body['items']), 3)

        # Check line totals
        self.assertEqual(body['items'][0]['line_total'], 10500.0)
        self.assertEqual(body['items'][1]['line_total'], 9000.0)
        self.assertEqual(body['items'][2]['line_total'], 8400.0)

        # Check variety summary format
        self.assertIn("(+2 more varieties)", order_header['variety'])

    # =========================================================================
    # 4. VALIDATION & ERROR HANDLING TESTS
    # =========================================================================

    def test_create_order_validation_failures(self):
        """Verifies clear error rejection on invalid order payloads."""
        self._login(self.client, 'supplier_rajesh')

        # 1. Missing nursery_user_id
        resp = self.client.post('/api/orders', json={"items": [{"plant_id": 1, "quantity": 10, "unit_price": 100}]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Client nursery partner", resp.get_json()['error'])

        # 2. Non-existent nursery_user_id
        resp = self.client.post('/api/orders', json={"nursery_user_id": 9999, "items": [{"plant_id": 1, "quantity": 10, "unit_price": 100}]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("does not exist", resp.get_json()['error'])

        # 3. Empty items array
        resp = self.client.post('/api/orders', json={"nursery_user_id": 2, "items": []})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("At least one plant line item is required", resp.get_json()['error'])

        # 4. Zero or negative quantity
        resp = self.client.post('/api/orders', json={"nursery_user_id": 2, "items": [{"plant_id": 1, "quantity": 0, "unit_price": 100}]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Quantity must be a positive whole integer", resp.get_json()['error'])

        # 5. Zero or negative price
        resp = self.client.post('/api/orders', json={"nursery_user_id": 2, "items": [{"plant_id": 1, "quantity": 15, "unit_price": -10}]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unit price must be greater than zero", resp.get_json()['error'])

        # 6. Non-existent plant_id
        resp = self.client.post('/api/orders', json={"nursery_user_id": 2, "items": [{"plant_id": 9999, "quantity": 15, "unit_price": 100}]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("does not exist in catalog", resp.get_json()['error'])

    # =========================================================================
    # 5. ORDER DETAILS RETRIEVAL & FILTERING TESTS
    # =========================================================================

    def test_get_order_details_endpoint(self):
        """GET /api/orders/<order_id> returns full order with itemized lines."""
        self._login(self.client, 'supplier_rajesh')
        resp = self.client.get('/api/orders/ORD-8801')
        self.assertEqual(resp.status_code, 200)
        details = resp.get_json()['data']

        self.assertEqual(details['order']['id'], 'ORD-8801')
        self.assertEqual(details['order']['variety'], 'Areca Palm (12-inch Pot)')
        self.assertGreaterEqual(len(details['items']), 1)
        self.assertEqual(details['items'][0]['line_total'], 52500.0)

    def test_get_order_details_nonexistent_returns_404(self):
        """Non-existent order ID returns 404 Not Found."""
        self._login(self.client, 'supplier_rajesh')
        resp = self.client.get('/api/orders/ORD-NONEXISTENT')
        self.assertEqual(resp.status_code, 404)

    def test_list_orders_filtering_and_search(self):
        """GET /api/orders supports status and search filters."""
        self._login(self.client, 'supplier_rajesh')

        # Filter by status = DISPATCHED
        resp_disp = self.client.get('/api/orders?status=DISPATCHED')
        self.assertEqual(resp_disp.status_code, 200)
        disp_orders = resp_disp.get_json()['data']
        for o in disp_orders:
            self.assertEqual(o['status'], 'DISPATCHED')

        # Search by variety 'Areca'
        resp_search = self.client.get('/api/orders?search=Areca')
        self.assertEqual(resp_search.status_code, 200)
        search_orders = resp_search.get_json()['data']
        self.assertTrue(any('Areca' in o['variety'] for o in search_orders))

    def test_nurseries_dropdown_endpoint(self):
        """GET /api/orders/nurseries returns list of registered nursery partners."""
        self._login(self.client, 'supplier_rajesh')
        resp = self.client.get('/api/orders/nurseries')
        self.assertEqual(resp.status_code, 200)
        nurseries = resp.get_json()['data']
        self.assertGreaterEqual(len(nurseries), 1)
        self.assertEqual(nurseries[0]['username'], 'nursery_amit')


if __name__ == '__main__':
    unittest.main()

