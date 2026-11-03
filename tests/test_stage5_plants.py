"""
FloraChain B2B — Test Suite: Phase 5 Plant Management Backend
Verifies:
- Listing wholesale plant catalog with pagination/filters/search
- Retrieving plant details by ID
- Creating new plant records (Supplier only, session-derived ownership)
- Updating existing plant records (Owner Supplier only)
- Validation rules (names, categories, sizes, units, prices, quantities, statuses)
- Unauthorized access rejection (401 unauthenticated, 403 role mismatch)
- Cross-supplier isolation (Supplier B cannot modify Supplier A's inventory)
- Private inventory privacy (Supplier B / Nursery cannot view another supplier's DISCONTINUED records)
- Non-existent plant retrieval/update handling (404)
- Existing database integrity & regressions
"""

import unittest
import os
import tempfile
import json
from werkzeug.security import generate_password_hash
from app import create_app
from app.models.database import get_connection


class TestPlantManagementBackend(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='_test_plants.db')
        self.app = create_app({
            'TESTING': True,
            'DB_PATH': self.db_path,
            'ALLOW_DEMO_ROLE_SWITCH': True,
            'SECRET_KEY': 'test_secret_plants_backend'
        })
        self.client = self.app.test_client()

        # Seed a second supplier to test multi-supplier ownership isolation
        conn = get_connection(self.db_path)
        with conn:
            conn.execute(
                """INSERT INTO users (username, email, password_hash, role, business_name)
                   VALUES (?, ?, ?, ?, ?)""",
                ('supplier_vikram', 'vikram@agrogrowers.com', generate_password_hash('password123'),
                 'SUPPLIER', 'Vikram Agro Growers')
            )
            vikram_id = conn.execute("SELECT id FROM users WHERE username = 'supplier_vikram'").fetchone()[0]

            # Create a plant owned by supplier_vikram
            conn.execute(
                """INSERT INTO plants
                   (common_name, botanical_name, category, container_size, unit, unit_price, stock_qty, min_order_qty, description, status, supplier_user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ('Rubber Plant Burgundy', 'Ficus elastica', 'INDOOR', '10-inch Pot', 'pot', 480.0, 50, 5, 'Glossy burgundy foliage', 'ACTIVE', vikram_id)
            )

            # Create a discontinued private plant owned by supplier_vikram
            conn.execute(
                """INSERT INTO plants
                   (common_name, botanical_name, category, container_size, unit, unit_price, stock_qty, min_order_qty, description, status, supplier_user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ('Rare Hybrid Orchid', 'Orchidaceae spec', 'FLOWERING', '6-inch Pot', 'pot', 1200.0, 0, 1, 'Private discontinued test crop', 'DISCONTINUED', vikram_id)
            )
        conn.close()

    def tearDown(self):
        try:
            os.close(self.db_fd)
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
            for suffix in ['-wal', '-shm']:
                wal = self.db_path + suffix
                if os.path.exists(wal):
                    os.unlink(wal)
        except OSError:
            pass

    def _login(self, username, password="password123"):
        return self.client.post('/api/auth/login', json={
            'username': username,
            'password': password
        })

    def _logout(self):
        return self.client.post('/api/auth/logout')

    # -------------------------------------------------------------------------
    # 1. LISTING & RETRIEVING PLANTS
    # -------------------------------------------------------------------------

    def test_list_plants_unauthenticated_fails(self):
        """Unauthenticated requests must be rejected with 401 Unauthorized."""
        res = self.client.get('/api/plants')
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data['success'])

    def test_list_plants_as_supplier(self):
        """Authenticated supplier can list wholesale plant records."""
        self._login('supplier_rajesh')
        res = self.client.get('/api/plants')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        # 6 demo plants for Rajesh + 1 active plant for Vikram = 7
        self.assertGreaterEqual(data['count'], 7)

    def test_list_plants_scope_mine(self):
        """Supplier listing with scope=mine sees only their own inventory."""
        self._login('supplier_rajesh')
        res = self.client.get('/api/plants?scope=mine')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['count'], 6)
        for p in data['data']:
            self.assertEqual(p['supplier_username'], 'supplier_rajesh')

    def test_list_plants_search_filter(self):
        """Searching by plant name returns relevant subset."""
        self._login('supplier_rajesh')
        res = self.client.get('/api/plants?q=Monstera')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['data'][0]['common_name'], 'Monstera Deliciosa')

    def test_list_plants_category_filter(self):
        """Filtering by category returns only matching category plants."""
        self._login('supplier_rajesh')
        res = self.client.get('/api/plants?category=PALM')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['data'][0]['common_name'], 'Areca Palm')

    def test_list_plants_status_filter(self):
        """Filtering by status returns matching status plants."""
        self._login('supplier_rajesh')
        res = self.client.get('/api/plants?status=ACTIVE')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        for p in data['data']:
            self.assertEqual(p['status'], 'ACTIVE')

    def test_get_plant_by_id_success(self):
        """Retrieving an existing plant by ID returns complete record."""
        self._login('supplier_rajesh')
        res = self.client.get('/api/plants/1')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['id'], 1)
        self.assertIn('common_name', data['data'])
        self.assertIn('supplier_name', data['data'])

    def test_get_plant_by_id_not_found(self):
        """Retrieving non-existent plant returns 404."""
        self._login('supplier_rajesh')
        res = self.client.get('/api/plants/999999')
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertFalse(data['success'])

    # -------------------------------------------------------------------------
    # 2. CREATING PLANTS
    # -------------------------------------------------------------------------

    def test_create_plant_supplier_success(self):
        """Authorized supplier can create a new plant record."""
        self._login('supplier_rajesh')
        payload = {
            'common_name': 'Snake Plant Laurentii',
            'botanical_name': 'Dracaena trifasciata',
            'category': 'INDOOR',
            'container_size': '8-inch Ceramic Pot',
            'unit': 'pot',
            'unit_price': 320.0,
            'stock_qty': 120,
            'min_order_qty': 10,
            'description': 'Hardy architectural indoor plant with golden-yellow margins.',
            'status': 'ACTIVE'
        }
        res = self.client.post('/api/plants', json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['common_name'], 'Snake Plant Laurentii')
        self.assertEqual(data['data']['unit_price'], 320.0)
        self.assertEqual(data['data']['stock_qty'], 120)
        self.assertEqual(data['data']['supplier_username'], 'supplier_rajesh')

    def test_create_plant_ignores_client_supplied_supplier_id(self):
        """Server must strictly derive supplier_user_id from the session, ignoring client payloads."""
        self._login('supplier_rajesh')
        payload = {
            'common_name': 'Money Plant Satin',
            'category': 'CLIMBER',
            'container_size': '6-inch Pot',
            'unit_price': 150.0,
            'supplier_user_id': 99999  # Spoofed client ID
        }
        res = self.client.post('/api/plants', json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        # Must be assigned to supplier_rajesh's actual user id, not 99999
        self.assertEqual(data['data']['supplier_username'], 'supplier_rajesh')

    def test_create_plant_unauthenticated_fails(self):
        """Unauthenticated user cannot create plant records."""
        res = self.client.post('/api/plants', json={'common_name': 'Test'})
        self.assertEqual(res.status_code, 401)

    def test_create_plant_nursery_role_fails(self):
        """Nursery user cannot create plant records (403 Forbidden)."""
        self._login('nursery_amit')
        payload = {
            'common_name': 'Bonsai Ficus',
            'category': 'ORNAMENTAL',
            'container_size': '8-inch Tray',
            'unit_price': 850.0
        }
        res = self.client.post('/api/plants', json=payload)
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])

    # -------------------------------------------------------------------------
    # 3. UPDATING PLANTS
    # -------------------------------------------------------------------------

    def test_update_plant_success(self):
        """Owner supplier can successfully update their plant record."""
        self._login('supplier_rajesh')
        update_payload = {
            'stock_qty': 490,
            'unit_price': 365.0,
            'description': 'Updated stock counts after fresh farm harvest.'
        }
        res = self.client.put('/api/plants/1', json=update_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['stock_qty'], 490)
        self.assertEqual(data['data']['unit_price'], 365.0)

    def test_update_plant_via_post_method(self):
        """Updates also supported via POST /api/plants/<id>."""
        self._login('supplier_rajesh')
        res = self.client.post('/api/plants/1', json={'stock_qty': 475})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['data']['stock_qty'], 475)

    def test_update_plant_not_found(self):
        """Updating non-existent plant returns 404."""
        self._login('supplier_rajesh')
        res = self.client.put('/api/plants/999999', json={'unit_price': 100.0})
        self.assertEqual(res.status_code, 404)

    # -------------------------------------------------------------------------
    # 4. CROSS-SUPPLIER ISOLATION & PRIVACY
    # -------------------------------------------------------------------------

    def test_supplier_cannot_update_another_suppliers_plant(self):
        """Supplier A cannot update Supplier B's plant (403 Forbidden)."""
        # Find plant owned by supplier_vikram
        conn = get_connection(self.db_path)
        vikram_plant = conn.execute(
            "SELECT p.id FROM plants p JOIN users u ON p.supplier_user_id = u.id WHERE u.username = 'supplier_vikram' LIMIT 1"
        ).fetchone()
        conn.close()
        plant_id = vikram_plant[0]

        # Login as supplier_rajesh and attempt to alter it
        self._login('supplier_rajesh')
        res = self.client.put(f'/api/plants/{plant_id}', json={'unit_price': 10.0})
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn("cannot modify another supplier's plant", data['error'])

    def test_supplier_cannot_inspect_another_suppliers_discontinued_plant(self):
        """Supplier A cannot view Supplier B's private discontinued plant record (403)."""
        conn = get_connection(self.db_path)
        disc_plant = conn.execute(
            "SELECT p.id FROM plants p JOIN users u ON p.supplier_user_id = u.id WHERE u.username = 'supplier_vikram' AND p.status = 'DISCONTINUED'"
        ).fetchone()
        conn.close()
        plant_id = disc_plant[0]

        # Login as supplier_rajesh
        self._login('supplier_rajesh')
        res = self.client.get(f'/api/plants/{plant_id}')
        self.assertEqual(res.status_code, 403)

    def test_nursery_cannot_view_discontinued_plants(self):
        """Nursery browsing catalog cannot see discontinued plants."""
        self._login('nursery_amit')
        res = self.client.get('/api/plants')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        for p in data['data']:
            self.assertNotEqual(p['status'], 'DISCONTINUED')

    # -------------------------------------------------------------------------
    # 5. INPUT VALIDATION & CONSTRAINT ENFORCEMENT
    # -------------------------------------------------------------------------

    def test_validation_empty_common_name(self):
        """Empty common name must be rejected with 422."""
        self._login('supplier_rajesh')
        res = self.client.post('/api/plants', json={
            'common_name': '   ',
            'category': 'INDOOR',
            'container_size': '6-inch Pot',
            'unit_price': 100.0
        })
        self.assertEqual(res.status_code, 422)

    def test_validation_invalid_category(self):
        """Invalid category string must be rejected with 422."""
        self._login('supplier_rajesh')
        res = self.client.post('/api/plants', json={
            'common_name': 'Test Plant',
            'category': 'NON_EXISTENT_CATEGORY',
            'container_size': '6-inch Pot',
            'unit_price': 100.0
        })
        self.assertEqual(res.status_code, 422)
        self.assertIn('Invalid category', res.get_json()['error'])

    def test_validation_negative_or_zero_price(self):
        """Negative or zero prices must be rejected."""
        self._login('supplier_rajesh')
        for bad_price in [0, -50.0, -0.01]:
            res = self.client.post('/api/plants', json={
                'common_name': 'Test Plant',
                'category': 'INDOOR',
                'container_size': '6-inch Pot',
                'unit_price': bad_price
            })
            self.assertEqual(res.status_code, 422)

    def test_validation_boolean_price_rejected(self):
        """Boolean passed as unit price must be rejected."""
        self._login('supplier_rajesh')
        res = self.client.post('/api/plants', json={
            'common_name': 'Test Plant',
            'category': 'INDOOR',
            'container_size': '6-inch Pot',
            'unit_price': True
        })
        self.assertEqual(res.status_code, 422)

    def test_validation_negative_stock(self):
        """Negative stock quantity must be rejected."""
        self._login('supplier_rajesh')
        res = self.client.post('/api/plants', json={
            'common_name': 'Test Plant',
            'category': 'INDOOR',
            'container_size': '6-inch Pot',
            'unit_price': 100.0,
            'stock_qty': -5
        })
        self.assertEqual(res.status_code, 422)

    def test_validation_invalid_unit(self):
        """Invalid unit must be rejected."""
        self._login('supplier_rajesh')
        res = self.client.post('/api/plants', json={
            'common_name': 'Test Plant',
            'category': 'INDOOR',
            'container_size': '6-inch Pot',
            'unit_price': 100.0,
            'unit': 'kilogram'
        })
        self.assertEqual(res.status_code, 422)

    def test_validation_invalid_status(self):
        """Invalid status must be rejected."""
        self._login('supplier_rajesh')
        res = self.client.post('/api/plants', json={
            'common_name': 'Test Plant',
            'category': 'INDOOR',
            'container_size': '6-inch Pot',
            'unit_price': 100.0,
            'status': 'ARCHIVED'
        })
        self.assertEqual(res.status_code, 422)

    def test_validation_empty_json_body(self):
        """Empty or non-JSON body returns 400 Bad Request."""
        self._login('supplier_rajesh')
        res = self.client.post('/api/plants', data="not json", content_type="text/plain")
        self.assertEqual(res.status_code, 400)


if __name__ == '__main__':
    unittest.main()

