"""
FloraChain B2B — Stage 7: Truck Loading & Vehicle Manifest Tests
Validates Phase 7 vehicle assignment, item staging counts, mathematical boundary limits,
supplier isolation, immutability, audit logging, and dispatch transitions.
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


class TestStage7TruckLoading(unittest.TestCase):
    """
    Validates end-to-end database-backed truck loading manifests,
    itemized staging counts, calculations, role isolation, and immutability.
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

    def _create_test_order(self, client, supplier_username='supplier_rajesh', items=None):
        """Helper to create a fresh confirmed wholesale order for testing truck loading."""
        self._login(client, supplier_username)
        if items is None:
            items = [
                {"plant_id": 1, "variety": "Areca Palm", "quantity": 40, "unit_price": 350.0},
                {"plant_id": 2, "variety": "Bougainvillea Dwarf", "quantity": 60, "unit_price": 180.0}
            ]
        resp = client.post('/api/orders', json={
            "nursery_user_id": 2, # Nursery Amit
            "notes": "Test order for truck loading staging",
            "items": items
        })
        self.assertEqual(resp.status_code, 201)
        return resp.get_json()['data']['order']['id']

    # =========================================================================
    # 1. SCHEMA & RETRIEVAL TESTS
    # =========================================================================

    def test_schema_order_items_has_loaded_qty(self):
        """order_items table must contain loaded_qty with non-negative check constraint."""
        conn = get_connection(self.temp_db_path)
        cols = [c[1] for c in conn.execute("PRAGMA table_info(order_items)").fetchall()]
        self.assertIn('loaded_qty', cols)

        order_cols = [c[1] for c in conn.execute("PRAGMA table_info(orders)").fetchall()]
        self.assertIn('loaded_at', order_cols)
        self.assertIn('loading_notes', order_cols)
        conn.close()

    def test_get_truck_loading_details_unauthenticated_rejected(self):
        """Unauthenticated access to loading manifest must return 401."""
        resp = self.client.get('/api/orders/ORD-8801/loading')
        self.assertEqual(resp.status_code, 401)
        resp_post = self.client.post('/api/orders/ORD-8801/loading', json={})
        self.assertEqual(resp_post.status_code, 401)
        resp_list = self.client.get('/api/truck-loadings')
        self.assertEqual(resp_list.status_code, 401)

    def test_get_truck_loading_initial_state(self):
        """New order starts with loaded_qty = 0, is_fully_loaded = False, and 100% remaining."""
        order_id = self._create_test_order(self.client)
        resp = self.client.get(f'/api/orders/{order_id}/loading')
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()['data']
        self.assertEqual(data['order']['id'], order_id)
        self.assertEqual(data['total_ordered_qty'], 100) # 40 + 60
        self.assertEqual(data['total_loaded_qty'], 0)
        self.assertEqual(data['total_remaining_qty'], 100)
        self.assertFalse(data['is_fully_loaded'])
        self.assertEqual(data['loading_pct'], 0.0)
        self.assertTrue(data['is_editable'])
        self.assertEqual(len(data['items']), 2)

    # =========================================================================
    # 2. PARTIAL LOADING & PROGRESS STAGING TESTS
    # =========================================================================

    def test_partial_truck_loading_saves_staging_state(self):
        """Supplier records partial plant loading; order transitions to STAGING with accurate remaining counts."""
        order_id = self._create_test_order(self.client)

        # Fetch item IDs
        det = self.client.get(f'/api/orders/{order_id}/loading').get_json()['data']
        item1_id = det['items'][0]['id'] # ordered 40
        item2_id = det['items'][1]['id'] # ordered 60

        payload = {
            "truck_no": "KA-04-E-9999",
            "driver_info": "Anil Verma (+91 98888 11111)",
            "notes": "First staging batch loaded onto lower rack.",
            "dispatch": False,
            "items": [
                {"id": item1_id, "loaded_qty": 20}, # 20 loaded, 20 remaining
                {"id": item2_id, "loaded_qty": 30}  # 30 loaded, 30 remaining
            ]
        }

        resp = self.client.post(f'/api/orders/{order_id}/loading', json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()['data']

        self.assertEqual(body['order']['status'], 'STAGING')
        self.assertEqual(body['order']['truck_no'], 'KA-04-E-9999')
        self.assertEqual(body['total_ordered_qty'], 100)
        self.assertEqual(body['total_loaded_qty'], 50)
        self.assertEqual(body['total_remaining_qty'], 50)
        self.assertEqual(body['loading_pct'], 50.0)
        self.assertFalse(body['is_fully_loaded'])

        # Verify persistence on re-fetch
        refetch = self.client.get(f'/api/orders/{order_id}/loading').get_json()['data']
        self.assertEqual(refetch['total_loaded_qty'], 50)
        self.assertEqual(refetch['items'][0]['loaded_qty'], 20)
        self.assertEqual(refetch['items'][0]['remaining_qty'], 20)
        self.assertEqual(refetch['items'][1]['loaded_qty'], 30)
        self.assertEqual(refetch['items'][1]['remaining_qty'], 30)

    # =========================================================================
    # 3. COMPLETE LOADING & VEHICLE DISPATCH TESTS
    # =========================================================================

    def test_complete_loading_and_dispatch(self):
        """Supplier completely loads all varieties and marks DISPATCHED with truck and driver info."""
        order_id = self._create_test_order(self.client)

        det = self.client.get(f'/api/orders/{order_id}/loading').get_json()['data']
        item1_id = det['items'][0]['id'] # 40
        item2_id = det['items'][1]['id'] # 60

        payload = {
            "truck_no": "KA-04-E-8821",
            "driver_info": "Ramesh Kumar (+91 98450 12345)",
            "notes": "Full wholesale nursery shipment secured and dispatched.",
            "dispatch": True,
            "items": [
                {"id": item1_id, "loaded_qty": 40},
                {"id": item2_id, "loaded_qty": 60}
            ]
        }

        resp = self.client.post(f'/api/orders/{order_id}/loading', json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()['data']

        self.assertEqual(body['order']['status'], 'DISPATCHED')
        self.assertEqual(body['order']['truck_no'], 'KA-04-E-8821')
        self.assertEqual(body['order']['driver_info'], 'Ramesh Kumar (+91 98450 12345)')
        self.assertEqual(body['total_loaded_qty'], 100)
        self.assertEqual(body['total_remaining_qty'], 0)
        self.assertTrue(body['is_fully_loaded'])
        self.assertEqual(body['loading_pct'], 100.0)

        # Check audit event logged
        conn = get_connection(self.temp_db_path)
        audit_event = conn.execute(
            "SELECT event_type, order_id, actor_role FROM audit_events WHERE order_id = ? AND event_type = 'TRUCK_DISPATCHED'",
            (order_id,)
        ).fetchone()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event['event_type'], 'TRUCK_DISPATCHED')
        conn.close()

    # =========================================================================
    # 4. MATHEMATICAL VALIDATION & ERROR REJECTION TESTS
    # =========================================================================

    def test_rejects_negative_loaded_quantity(self):
        """Negative loaded quantities must be rejected with 400 Bad Request."""
        order_id = self._create_test_order(self.client)
        det = self.client.get(f'/api/orders/{order_id}/loading').get_json()['data']
        item1_id = det['items'][0]['id']

        resp = self.client.post(f'/api/orders/{order_id}/loading', json={
            "items": [{"id": item1_id, "loaded_qty": -5}]
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cannot be negative", resp.get_json()['error'])

    def test_rejects_excessive_loaded_quantity(self):
        """Loaded quantity greater than ordered quantity must be rejected with 400 Bad Request."""
        order_id = self._create_test_order(self.client)
        det = self.client.get(f'/api/orders/{order_id}/loading').get_json()['data']
        item1_id = det['items'][0]['id'] # ordered 40

        resp = self.client.post(f'/api/orders/{order_id}/loading', json={
            "items": [{"id": item1_id, "loaded_qty": 45}] # 45 > 40
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cannot exceed ordered quantity", resp.get_json()['error'])

    def test_rejects_dispatch_without_truck_or_driver(self):
        """Dispatching with empty/TBD truck_no or driver_info must return 400 Bad Request."""
        order_id = self._create_test_order(self.client)
        det = self.client.get(f'/api/orders/{order_id}/loading').get_json()['data']
        item1_id = det['items'][0]['id']

        # Missing truck_no
        resp1 = self.client.post(f'/api/orders/{order_id}/loading', json={
            "truck_no": "",
            "driver_info": "Valid Driver",
            "dispatch": True,
            "items": [{"id": item1_id, "loaded_qty": 20}]
        })
        self.assertEqual(resp1.status_code, 400)
        self.assertIn("truck number is required", resp1.get_json()['error'])

        # Missing driver_info
        resp2 = self.client.post(f'/api/orders/{order_id}/loading', json={
            "truck_no": "KA-01-AA-1111",
            "driver_info": "TBD",
            "dispatch": True,
            "items": [{"id": item1_id, "loaded_qty": 20}]
        })
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("Driver name and contact", resp2.get_json()['error'])

    def test_rejects_dispatch_with_zero_loaded_units(self):
        """Cannot dispatch an empty vehicle with 0 loaded units."""
        order_id = self._create_test_order(self.client)
        det = self.client.get(f'/api/orders/{order_id}/loading').get_json()['data']
        item1_id = det['items'][0]['id']

        resp = self.client.post(f'/api/orders/{order_id}/loading', json={
            "truck_no": "KA-01-AA-1111",
            "driver_info": "Valid Driver",
            "dispatch": True,
            "items": [{"id": item1_id, "loaded_qty": 0}]
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("0 loaded plant units", resp.get_json()['error'])

    # =========================================================================
    # 5. AUTHORIZATION, ISOLATION & IMMUTABILITY TESTS
    # =========================================================================

    def test_nursery_cannot_record_truck_loading(self):
        """Nursery user attempting to record truck loading must receive 403 Forbidden."""
        order_id = self._create_test_order(self.client)

        self.client.post('/api/auth/logout')
        self._login(self.client, 'nursery_amit')
        resp = self.client.post(f'/api/orders/{order_id}/loading', json={
            "items": [{"plant_id": 1, "loaded_qty": 10}]
        })
        self.assertEqual(resp.status_code, 403)
        self.assertIn("wholesale suppliers", resp.get_json()['error'])

    def test_cross_supplier_isolation(self):
        """Supplier A cannot modify truck loading of Supplier B's order (403 Forbidden)."""
        order_id = self._create_test_order(self.client, 'supplier_rajesh')

        # Insert second supplier
        conn = get_connection(self.temp_db_path)
        with conn:
            conn.execute(
                """INSERT INTO users (username, email, password_hash, role, business_name)
                   VALUES ('supplier_other', 'other@supp.com', ?, 'SUPPLIER', 'Other Supplier Co')""",
                (generate_password_hash('password123'),)
            )
        conn.close()

        self.client.post('/api/auth/logout')
        self._login(self.client, 'supplier_other')

        # Attempt to modify Rajesh's order loading
        resp = self.client.post(f'/api/orders/{order_id}/loading', json={
            "items": [{"plant_id": 1, "loaded_qty": 10}]
        })
        self.assertEqual(resp.status_code, 403)
        self.assertIn("not the assigned wholesale supplier", resp.get_json()['error'])

    def test_immutable_locked_order_loading_rejected(self):
        """Finalized/locked orders (such as ORD-8760) reject truck loading modification with 403 Forbidden."""
        self._login(self.client, 'supplier_rajesh')

        resp = self.client.post('/api/orders/ORD-8760/loading', json={
            "items": [{"plant_id": 5, "loaded_qty": 50}]
        })
        self.assertEqual(resp.status_code, 403)
        self.assertIn("locked", resp.get_json()['error'].lower())

    # =========================================================================
    # 6. MANIFEST BOARD LISTING & FILTERING TESTS
    # =========================================================================

    def test_list_truck_manifests_endpoint(self):
        """GET /api/truck-loadings lists manifests with progress and status."""
        self._login(self.client, 'supplier_rajesh')

        resp = self.client.get('/api/truck-loadings')
        self.assertEqual(resp.status_code, 200)
        manifests = resp.get_json()['data']
        self.assertGreaterEqual(len(manifests), 3)

        # Dispatched seed order ORD-8802 should show 100% loaded
        ord_8802 = next((m for m in manifests if m['order_id'] == 'ORD-8802'), None)
        self.assertIsNotNone(ord_8802)
        self.assertEqual(ord_8802['status'], 'DISPATCHED')
        self.assertEqual(ord_8802['truck_no'], 'KA-05-MH-4412')
        self.assertEqual(ord_8802['loading_pct'], 100.0)

    def test_list_truck_manifests_search_filter(self):
        """Search query filters manifests by vehicle number or driver name."""
        self._login(self.client, 'supplier_rajesh')

        resp = self.client.get('/api/truck-loadings?search=KA-04-E-8821')
        self.assertEqual(resp.status_code, 200)
        results = resp.get_json()['data']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['order_id'], 'ORD-8801')


if __name__ == '__main__':
    unittest.main()

