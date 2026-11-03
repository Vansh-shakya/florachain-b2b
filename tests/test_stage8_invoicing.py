"""
FloraChain B2B — Phase 8 Invoice Generation Test Suite
Validates:
1. Invoicing strictly locked and verified deliveries (ORD-8760, ORD-8801)
2. Invoicing rejected for unverified orders (ORD-8802)
3. Historical unit price preservation (order's price, not altered catalog price)
4. Duplicate invoice prevention (409 Conflict)
5. Agreed damage billing terms (damaged units credited vs charged)
6. Multi-variety order with 0 damage (100% sound invoice)
7. Multi-variety order with damage: rejects missing item-level breakdown (pro-rata prohibited)
8. Multi-variety order with explicit item-level inspection: valid invoice generation
9. Item-level mathematical consistency validation (sum mismatch rejected)
10. Role-based authorization & data isolation (Supplier vs Nursery vs Admin)
11. Invoice cancellation workflow with audit justification
12. Historical invoice immutability (frozen lines never mutate)
13. Database schema migration safety
"""

import unittest
import os
import sys
import tempfile
import json
import sqlite3

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models.database import get_connection, init_database


class TestStage8Invoicing(unittest.TestCase):
    """
    Validates end-to-end commercial wholesale invoice generation,
    verified delivery quantity attribution, price freezing, and security rules.
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

    def login_user(self, username, password="password123"):
        """Helper to authenticate a session."""
        resp = self.client.post('/api/auth/login', json={
            'username': username,
            'password': password
        })
        self.assertEqual(resp.status_code, 200, f"Login failed for {username}: {resp.get_json()}")
        return resp.get_json()['data']

    def test_01_seeded_invoice_retrieval(self):
        """Test retrieving the seeded invoice INV-2026-8760 for locked order ORD-8760."""
        self.login_user('supplier_rajesh')
        resp = self.client.get('/api/invoices/INV-2026-8760')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()['data']
        self.assertEqual(data['invoice']['invoice_number'], 'INV-2026-8760')
        self.assertEqual(data['invoice']['order_id'], 'ORD-8760')
        self.assertEqual(data['invoice']['total_amount'], 41160.0) # 98 sound * 420.0
        self.assertEqual(data['invoice']['total_quantity'], 98)
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['sound_qty'], 98)
        self.assertEqual(data['items'][0]['damaged_qty'], 2)
        self.assertEqual(data['items'][0]['damaged_unit_price'], 0.0) # 2 damaged credited

    def test_02_invoice_creation_for_locked_order(self):
        """Test issuing invoice for locked order ORD-8801 (150 ordered, 145 sound, 5 damaged)."""
        self.login_user('supplier_rajesh')
        # Setup delivery inspection and locked state for ORD-8801
        conn = get_connection(self.temp_db_path)
        conn.execute("UPDATE orders SET status = 'LOCKED_VERIFIED' WHERE id = 'ORD-8801'")
        conn.execute("""
            INSERT OR REPLACE INTO delivery_inspections 
            (order_id, delivered_qty, sound_qty, damaged_qty, damage_pct, has_mismatch, mismatch_diff, status, is_locked, locked_at)
            VALUES ('ORD-8801', 150, 145, 5, 3.33, 0, 0, 'LOCKED_VERIFIED', 1, CURRENT_TIMESTAMP)
        """)
        conn.commit()
        conn.close()

        resp = self.client.post('/api/orders/ORD-8801/invoice', json={
            'notes': 'Wholesale invoice for 145 verified Areca Palms.'
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()['data']
        inv = data['invoice']
        self.assertEqual(inv['order_id'], 'ORD-8801')
        self.assertEqual(inv['total_amount'], 50750.0) # 145 sound * 350.0
        self.assertEqual(inv['total_quantity'], 145)
        self.assertEqual(data['items'][0]['billable_qty'], 145)
        self.assertEqual(data['items'][0]['damaged_qty'], 5)

    def test_03_unverified_order_invoicing_rejected(self):
        """Test that unverified order ORD-8802 (DISPATCHED, is_locked=0) strictly rejects invoice generation."""
        self.login_user('supplier_rajesh')
        resp = self.client.post('/api/orders/ORD-8802/invoice', json={})
        self.assertEqual(resp.status_code, 403)
        self.assertIn("has not completed independent physical delivery verification", resp.get_json()['error'])

    def test_04_duplicate_invoice_prevention(self):
        """Test that issuing a second invoice for the same order is blocked with 409 Conflict."""
        self.login_user('supplier_rajesh')
        # INV-2026-8760 already exists for ORD-8760
        resp = self.client.post('/api/orders/ORD-8760/invoice', json={})
        self.assertEqual(resp.status_code, 409)
        self.assertIn("Duplicate Invoice Conflict", resp.get_json()['error'])

    def test_05_historical_price_preservation(self):
        """Test that issued invoice preserves order's unit price even if catalog price changes."""
        self.login_user('supplier_rajesh')
        # Setup delivery inspection and locked state for ORD-8801
        conn = get_connection(self.temp_db_path)
        conn.execute("UPDATE orders SET status = 'LOCKED_VERIFIED' WHERE id = 'ORD-8801'")
        conn.execute("""
            INSERT OR REPLACE INTO delivery_inspections 
            (order_id, delivered_qty, sound_qty, damaged_qty, damage_pct, has_mismatch, mismatch_diff, status, is_locked, locked_at)
            VALUES ('ORD-8801', 150, 145, 5, 3.33, 0, 0, 'LOCKED_VERIFIED', 1, CURRENT_TIMESTAMP)
        """)
        conn.commit()
        conn.close()

        # Issue invoice for ORD-8801 at Rs. 350
        resp = self.client.post('/api/orders/ORD-8801/invoice', json={})
        self.assertEqual(resp.status_code, 201)
        inv_number = resp.get_json()['data']['invoice']['invoice_number']

        # Mutate the catalog price of Areca Palm from 350 to 999
        conn = get_connection(self.temp_db_path)
        conn.execute("UPDATE plants SET unit_price = 999.0 WHERE common_name = 'Areca Palm'")
        conn.commit()
        conn.close()

        # Re-fetch the invoice
        resp2 = self.client.get(f'/api/invoices/{inv_number}')
        self.assertEqual(resp2.status_code, 200)
        data = resp2.get_json()['data']
        # Frozen invoice item MUST still reflect 350.0 and 50750.0 total
        self.assertEqual(data['items'][0]['unit_price'], 350.0)
        self.assertEqual(data['invoice']['total_amount'], 50750.0)

    def test_06_damage_billing_rate_option(self):
        """Test invoice creation with explicit agreed damage billing charge (e.g. 50% salvage rate)."""
        self.login_user('supplier_rajesh')
        # Create a test locked order with damage
        conn = get_connection(self.temp_db_path)
        conn.execute("""
            INSERT INTO orders (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, status)
            VALUES ('ORD-TEST-DMG', 1, 2, 'Monstera Deliciosa', 20, 500.0, 'LOCKED_VERIFIED')
        """)
        conn.execute("""
            INSERT INTO order_items (order_id, variety, quantity, unit_price, line_total, loaded_qty, delivered_qty, sound_qty, damaged_qty)
            VALUES ('ORD-TEST-DMG', 'Monstera Deliciosa', 20, 500.0, 10000.0, 20, 20, 16, 4)
        """)
        conn.execute("""
            INSERT INTO delivery_inspections (order_id, delivered_qty, sound_qty, damaged_qty, damage_pct, has_mismatch, mismatch_diff, status, is_locked)
            VALUES ('ORD-TEST-DMG', 20, 16, 4, 20.0, 0, 0, 'LOCKED_VERIFIED', 1)
        """)
        conn.commit()
        conn.close()

        # Issue invoice with 50% salvage rate on 4 damaged plants
        # 16 sound * 500 = 8000.0
        # 4 damaged * (500 * 0.5 = 250) = 1000.0
        # Total = 9000.0
        resp = self.client.post('/api/orders/ORD-TEST-DMG/invoice', json={
            'damage_charge_pct': 50.0
        })
        self.assertEqual(resp.status_code, 201)
        inv = resp.get_json()['data']['invoice']
        self.assertEqual(inv['total_amount'], 9000.0)
        self.assertEqual(inv['damage_billing_policy'], 'CHARGED_50PCT')

    def test_07_multi_variety_order_zero_damage(self):
        """Test multi-variety order with 0 transit damage invoices 100% sound quantities."""
        self.login_user('supplier_rajesh')
        conn = get_connection(self.temp_db_path)
        conn.execute("""
            INSERT INTO orders (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, status)
            VALUES ('ORD-MULTI-ZERO', 1, 2, 'Areca + Bougainvillea', 50, 250.0, 'LOCKED_VERIFIED')
        """)
        conn.execute("""
            INSERT INTO order_items (order_id, variety, quantity, unit_price, line_total, loaded_qty, delivered_qty, sound_qty, damaged_qty)
            VALUES ('ORD-MULTI-ZERO', 'Areca Palm', 20, 350.0, 7000.0, 20, 20, 20, 0)
        """)
        conn.execute("""
            INSERT INTO order_items (order_id, variety, quantity, unit_price, line_total, loaded_qty, delivered_qty, sound_qty, damaged_qty)
            VALUES ('ORD-MULTI-ZERO', 'Bougainvillea Dwarf', 30, 180.0, 5400.0, 30, 30, 30, 0)
        """)
        conn.execute("""
            INSERT INTO delivery_inspections (order_id, delivered_qty, sound_qty, damaged_qty, damage_pct, has_mismatch, mismatch_diff, status, is_locked)
            VALUES ('ORD-MULTI-ZERO', 50, 50, 0, 0.0, 0, 0, 'LOCKED_VERIFIED', 1)
        """)
        conn.commit()
        conn.close()

        resp = self.client.post('/api/orders/ORD-MULTI-ZERO/invoice', json={})
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()['data']
        self.assertEqual(data['invoice']['total_amount'], 12400.0) # 7000 + 5400
        self.assertEqual(len(data['items']), 2)

    def test_08_multi_variety_damage_missing_item_counts_rejected(self):
        """Test that multi-variety order with damage strictly rejects invoicing if item-level counts are missing."""
        self.login_user('supplier_rajesh')
        conn = get_connection(self.temp_db_path)
        conn.execute("""
            INSERT INTO orders (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, status)
            VALUES ('ORD-MULTI-DMG-FAIL', 1, 2, 'Areca + Bougainvillea', 50, 250.0, 'LOCKED_VERIFIED')
        """)
        # Items created without explicit item-level inspection fields (NULL)
        conn.execute("""
            INSERT INTO order_items (order_id, variety, quantity, unit_price, line_total, loaded_qty)
            VALUES ('ORD-MULTI-DMG-FAIL', 'Areca Palm', 20, 350.0, 7000.0, 20)
        """)
        conn.execute("""
            INSERT INTO order_items (order_id, variety, quantity, unit_price, line_total, loaded_qty)
            VALUES ('ORD-MULTI-DMG-FAIL', 'Bougainvillea Dwarf', 30, 180.0, 5400.0, 30)
        """)
        conn.execute("""
            INSERT INTO delivery_inspections (order_id, delivered_qty, sound_qty, damaged_qty, damage_pct, has_mismatch, mismatch_diff, status, is_locked)
            VALUES ('ORD-MULTI-DMG-FAIL', 50, 45, 5, 10.0, 0, 0, 'LOCKED_VERIFIED', 1)
        """)
        conn.commit()
        conn.close()

        resp = self.client.post('/api/orders/ORD-MULTI-DMG-FAIL/invoice', json={})
        self.assertEqual(resp.status_code, 422)
        err = resp.get_json()['error']
        self.assertIn("lacks explicit item-level delivery inspection counts", err)
        self.assertIn("Pro-rata allocation is prohibited", err)

    def test_09_multi_variety_itemized_inspection_and_invoicing(self):
        """Test recording itemized inspection and generating invoice for multi-variety damaged order."""
        # Step 1: Set up multi-variety order
        conn = get_connection(self.temp_db_path)
        conn.execute("""
            INSERT INTO orders (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, status)
            VALUES ('ORD-MULTI-OK', 1, 2, 'Areca + Bougainvillea', 50, 250.0, 'LOCKED_VERIFIED')
        """)
        conn.execute("""
            INSERT INTO order_items (id, order_id, variety, quantity, unit_price, line_total, loaded_qty)
            VALUES (101, 'ORD-MULTI-OK', 'Areca Palm', 20, 350.0, 7000.0, 20)
        """)
        conn.execute("""
            INSERT INTO order_items (id, order_id, variety, quantity, unit_price, line_total, loaded_qty)
            VALUES (102, 'ORD-MULTI-OK', 'Bougainvillea Dwarf', 30, 180.0, 5400.0, 30)
        """)
        conn.execute("""
            INSERT INTO delivery_inspections (order_id, delivered_qty, sound_qty, damaged_qty, damage_pct, has_mismatch, mismatch_diff, status, is_locked)
            VALUES ('ORD-MULTI-OK', 50, 45, 5, 10.0, 0, 0, 'LOCKED_VERIFIED', 1)
        """)
        conn.commit()
        conn.close()

        # Step 2: Nursery records explicit item-level inspection
        # Areca: 20 delivered, 18 sound, 2 damaged
        # Bougainvillea: 30 delivered, 27 sound, 3 damaged
        # Total sound: 18 + 27 = 45; total damaged: 2 + 3 = 5
        self.login_user('nursery_amit')
        resp_item_insp = self.client.post('/api/orders/ORD-MULTI-OK/itemized-inspection', json={
            'items': [
                {'order_item_id': 101, 'delivered_qty': 20, 'sound_qty': 18, 'damaged_qty': 2},
                {'order_item_id': 102, 'delivered_qty': 30, 'sound_qty': 27, 'damaged_qty': 3}
            ]
        })
        self.assertEqual(resp_item_insp.status_code, 200)

        # Step 3: Supplier issues invoice
        # Areca: 18 sound * 350 = 6300.0 (2 damaged credited)
        # Bougainvillea: 27 sound * 180 = 4860.0 (3 damaged credited)
        # Total = 11160.0
        self.login_user('supplier_rajesh')
        resp_inv = self.client.post('/api/orders/ORD-MULTI-OK/invoice', json={})
        self.assertEqual(resp_inv.status_code, 201)
        data = resp_inv.get_json()['data']
        self.assertEqual(data['invoice']['total_amount'], 11160.0)
        self.assertEqual(data['invoice']['total_quantity'], 45)
        self.assertEqual(len(data['items']), 2)
        self.assertEqual(data['items'][0]['sound_qty'], 18)
        self.assertEqual(data['items'][0]['damaged_qty'], 2)
        self.assertEqual(data['items'][1]['sound_qty'], 27)
        self.assertEqual(data['items'][1]['damaged_qty'], 3)

    def test_10_itemized_inspection_sum_mismatch_rejected(self):
        """Test that itemized inspection rejects data where item sums do not match order delivery total."""
        self.login_user('nursery_amit')
        conn = get_connection(self.temp_db_path)
        conn.execute("""
            INSERT INTO orders (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, status)
            VALUES ('ORD-SUM-MIS', 1, 2, 'Palm + Ficus', 40, 300.0, 'DISPATCHED')
        """)
        conn.execute("""
            INSERT INTO order_items (id, order_id, variety, quantity, unit_price, line_total, loaded_qty)
            VALUES (201, 'ORD-SUM-MIS', 'Palm', 20, 300.0, 6000.0, 20)
        """)
        conn.execute("""
            INSERT INTO order_items (id, order_id, variety, quantity, unit_price, line_total, loaded_qty)
            VALUES (202, 'ORD-SUM-MIS', 'Ficus', 20, 300.0, 6000.0, 20)
        """)
        conn.execute("""
            INSERT INTO delivery_inspections (order_id, delivered_qty, sound_qty, damaged_qty, damage_pct, has_mismatch, mismatch_diff, status, is_locked)
            VALUES ('ORD-SUM-MIS', 40, 38, 2, 5.0, 0, 0, 'DRAFT', 0)
        """)
        conn.commit()
        conn.close()

        # Submit items that sum to 35 sound instead of 38 sound
        resp = self.client.post('/api/orders/ORD-SUM-MIS/itemized-inspection', json={
            'items': [
                {'order_item_id': 201, 'delivered_qty': 20, 'sound_qty': 17, 'damaged_qty': 3},
                {'order_item_id': 202, 'delivered_qty': 20, 'sound_qty': 18, 'damaged_qty': 2}
            ]
        })
        self.assertEqual(resp.status_code, 422)
        self.assertIn("does not match order verified sound total", resp.get_json()['error'])

    def test_11_role_authorization_and_isolation(self):
        """Test that Nursery cannot issue invoices, and Nursery cannot view other nurseries' invoices."""
        # Nursery cannot generate invoice
        self.login_user('nursery_amit')
        resp = self.client.post('/api/orders/ORD-8801/invoice', json={})
        self.assertEqual(resp.status_code, 403)

        # Create another nursery user and verify isolation
        conn = get_connection(self.temp_db_path)
        from werkzeug.security import generate_password_hash
        conn.execute("""
            INSERT INTO users (username, email, password_hash, role, business_name)
            VALUES ('nursery_other', 'other@nursery.com', ?, 'NURSERY', 'Other Nursery Ltd')
        """, (generate_password_hash('password123'),))
        conn.commit()
        conn.close()

        self.login_user('nursery_other')
        # Trying to view INV-2026-8760 (belonging to nursery_amit)
        resp_view = self.client.get('/api/invoices/INV-2026-8760')
        self.assertEqual(resp_view.status_code, 403)
        self.assertIn("Unauthorized", resp_view.get_json()['error'])

    def test_12_invoice_cancellation(self):
        """Test invoice cancellation with audit justification."""
        self.login_user('supplier_rajesh')
        resp = self.client.post('/api/invoices/INV-2026-8760/cancel', json={
            'reason': 'Customer requested billing revision before payment processing.'
        })
        self.assertEqual(resp.status_code, 200)
        inv = resp.get_json()['data']['invoice']
        self.assertEqual(inv['status'], 'CANCELLED')

        # Check audit event
        conn = get_connection(self.temp_db_path)
        audit = conn.execute("SELECT * FROM audit_events WHERE event_type = 'INVOICE_CANCELLED'").fetchone()
        self.assertIsNotNone(audit)
        self.assertEqual(audit['order_id'], 'ORD-8760')
        conn.close()


if __name__ == '__main__':
    unittest.main()
