"""
FloraChain B2B — Stage 3 Database-Backed Delivery Verification Test Suite
Tests:
1. Nursery physical arrival inspection creation and validation
2. Supplier counter-signature and atomic locking (dual confirmation)
3. Data persistence across application / database connection restarts
4. Order ownership and role authorization enforcement (unassigned parties rejected)
5. Administrators strictly barred from satisfying party delivery confirmations
6. Duplicate confirmation prevention (409 Conflict via UNIQUE constraint)
7. Mathematical quantity validations (negatives, non-integers, sum mismatch)
8. Original ordered_qty immutability (discrepancy flagged without modifying order)
9. Rejection of direct API edit attempts on finalized locked orders (403 Forbidden)
10. Rejection of direct confirmation attempts on locked orders (403 Forbidden)
11. Unauthenticated request protection across all inspection endpoints (401 Unauthorized)
12. Concurrent / duplicate confirmation conflict resilience
13. Untrusted legacy localStorage import behavior (never pre-verified or locked)
"""

import unittest
import os
import sys
import tempfile
import json
import sqlite3
from werkzeug.security import generate_password_hash

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models.database import get_connection

class TestStage3DeliveryVerification(unittest.TestCase):
    """
    Validates end-to-end database-backed physical delivery verification,
    independent dual confirmations, server-side locking, and security boundaries.
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
        """Helper to establish an authenticated session for a specific user."""
        resp = self.client.post('/api/auth/login', json={
            'username': username,
            'password': password
        })
        self.assertEqual(resp.status_code, 200, f"Login failed for {username}: {resp.get_json()}")
        return resp.get_json()['data']

    def test_unauthenticated_requests_blocked(self):
        """All inspection and confirmation endpoints must reject unauthenticated requests with 401."""
        self.assertEqual(self.client.get('/api/orders').status_code, 401)
        self.assertEqual(self.client.get('/api/orders/ORD-8801').status_code, 401)
        self.assertEqual(self.client.post('/api/orders/ORD-8801/inspection', json={}).status_code, 401)
        self.assertEqual(self.client.post('/api/orders/ORD-8801/confirm', json={}).status_code, 401)
        self.assertEqual(self.client.post('/api/inspections/import-local', json={}).status_code, 401)

    def test_nursery_initial_inspection_and_confirmation(self):
        """
        Nursery submits physical intake counts for ORD-8801:
        - Validates sound + damaged == delivered
        - Transitions order to INSPECTED_PENDING_CONFIRMATION
        - Sets inspection status to PENDING_SUPPLIER_CONFIRMATION
        - is_locked remains 0 (not locked until supplier counter-signs)
        """
        self.login_user('nursery_amit')

        resp = self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 150,
            'sound_qty': 145,
            'damaged_qty': 5,
            'damage_notes': '5 pots cracked in transit; nursery intake verified.'
        })

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()['data']

        self.assertEqual(data['order']['status'], 'INSPECTED_PENDING_CONFIRMATION')
        self.assertEqual(data['status'], 'PENDING_SUPPLIER_CONFIRMATION')
        self.assertFalse(data['is_locked'])
        self.assertTrue(data['nursery_confirmed'])
        self.assertFalse(data['supplier_confirmed'])
        self.assertEqual(data['inspection']['sound_qty'], 145)
        self.assertEqual(data['inspection']['damaged_qty'], 5)
        self.assertEqual(data['inspection']['damage_pct'], 3.33)

        # Verify confirmation record
        self.assertEqual(len(data['confirmations']), 1)
        self.assertEqual(data['confirmations'][0]['party_role'], 'NURSERY')
        self.assertEqual(data['confirmations'][0]['user_name'], 'nursery_amit')

    def test_supplier_counter_sign_and_atomic_locking(self):
        """
        Full dual-confirmation workflow:
        1. Nursery records counts -> PENDING_SUPPLIER_CONFIRMATION
        2. Supplier logs in and counter-signs -> Both parties confirmed -> ATOMIC LOCK
        3. is_locked flips to True, status flips to LOCKED_VERIFIED
        """
        # Step 1: Nursery records dock inspection
        self.login_user('nursery_amit')
        resp1 = self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 150,
            'sound_qty': 145,
            'damaged_qty': 5,
            'damage_notes': '5 damaged units noted.'
        })
        self.assertEqual(resp1.status_code, 200)

        # Step 2: Supplier logs in and counter-signs
        self.login_user('supplier_rajesh')
        resp2 = self.client.post('/api/orders/ORD-8801/confirm', json={
            'party_role': 'SUPPLIER',
            'signature_note': 'Counter-signed by dispatch manager Rajesh Kumar; 5 unit credit acknowledged.'
        })
        self.assertEqual(resp2.status_code, 200)
        data = resp2.get_json()['data']

        # Step 3: Verify atomic lock
        self.assertTrue(data['is_locked'])
        self.assertEqual(data['status'], 'LOCKED_VERIFIED')
        self.assertEqual(data['order']['status'], 'LOCKED_VERIFIED')
        self.assertTrue(data['nursery_confirmed'])
        self.assertTrue(data['supplier_confirmed'])
        self.assertEqual(len(data['confirmations']), 2)

        # Verify audit trail contains ORDER_LOCKED
        resp_audit = self.client.get('/api/orders/ORD-8801/audit')
        self.assertEqual(resp_audit.status_code, 200)
        events = resp_audit.get_json()['data']
        event_types = [e['event_type'] for e in events]
        self.assertIn('INSPECTION_CREATED', event_types)
        self.assertIn('SUPPLIER_CONFIRMED', event_types)
        self.assertIn('ORDER_LOCKED', event_types)

    def test_persistence_across_app_restarts(self):
        """
        Database persistence test:
        Records confirmed and locked survive complete application restart and connection pooling.
        """
        # Execute dual confirmation
        self.login_user('nursery_amit')
        self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 150,
            'sound_qty': 145,
            'damaged_qty': 5,
            'damage_notes': 'Intake check.'
        })
        self.login_user('supplier_rajesh')
        self.client.post('/api/orders/ORD-8801/confirm', json={'party_role': 'SUPPLIER'})

        # Simulate full server restart:
        # Re-initialize create_app on the exact same database file
        new_app = create_app({'DB_PATH': self.temp_db_path, 'ALLOW_DEMO_ROLE_SWITCH': True})
        new_client = new_app.test_client()

        # Login on new client
        new_client.post('/api/auth/login', json={'username': 'supplier_rajesh', 'password': 'password123'})

        # Fetch order details
        resp = new_client.get('/api/orders/ORD-8801')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()['data']

        self.assertTrue(data['is_locked'])
        self.assertEqual(data['status'], 'LOCKED_VERIFIED')
        self.assertEqual(data['inspection']['sound_qty'], 145)
        self.assertEqual(data['inspection']['damaged_qty'], 5)
        self.assertEqual(len(data['confirmations']), 2)

    def test_order_authorization_unassigned_nursery_rejected(self):
        """A nursery user not assigned to the order must receive 403 Forbidden."""
        # Insert a second nursery user into the database
        conn = get_connection(self.temp_db_path)
        with conn:
            conn.execute(
                """INSERT INTO users (username, email, password_hash, role, business_name)
                   VALUES ('nursery_other', 'other@nursery.com', ?, 'NURSERY', 'Other Nursery Ltd')""",
                (generate_password_hash('password123'),)
            )
        conn.close()

        # Login as the unassigned nursery
        self.login_user('nursery_other')

        # Attempt to inspect ORD-8801 (assigned to nursery_amit)
        resp = self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 150,
            'sound_qty': 150,
            'damaged_qty': 0
        })
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Unauthorized: You are not the assigned nursery', resp.get_json()['error'])

    def test_order_authorization_unassigned_supplier_rejected(self):
        """A supplier user not assigned to the order must receive 403 Forbidden."""
        # First record valid nursery inspection
        self.login_user('nursery_amit')
        self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 150,
            'sound_qty': 150,
            'damaged_qty': 0
        })

        # Insert a second supplier user into the database
        conn = get_connection(self.temp_db_path)
        with conn:
            conn.execute(
                """INSERT INTO users (username, email, password_hash, role, business_name)
                   VALUES ('supplier_other', 'other@supplier.com', ?, 'SUPPLIER', 'Other Wholesale Farms')""",
                (generate_password_hash('password123'),)
            )
        conn.close()

        # Login as unassigned supplier
        self.login_user('supplier_other')

        # Attempt to counter-sign ORD-8801 (assigned to supplier_rajesh)
        resp = self.client.post('/api/orders/ORD-8801/confirm', json={'party_role': 'SUPPLIER'})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Unauthorized: You are not the assigned supplier', resp.get_json()['error'])

    def test_admin_cannot_counter_sign_delivery(self):
        """Administrators are strictly forbidden from counter-signing delivery inspections."""
        self.login_user('nursery_amit')
        self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 150,
            'sound_qty': 150,
            'damaged_qty': 0
        })

        # Login as Administrator
        self.login_user('admin_flora')

        # Attempt to counter-sign as NURSERY
        resp_nurs = self.client.post('/api/orders/ORD-8801/confirm', json={'party_role': 'NURSERY'})
        self.assertEqual(resp_nurs.status_code, 403)
        self.assertIn('Administrators cannot impersonate either party', resp_nurs.get_json()['error'])

        # Attempt to counter-sign as SUPPLIER
        resp_supp = self.client.post('/api/orders/ORD-8801/confirm', json={'party_role': 'SUPPLIER'})
        self.assertEqual(resp_supp.status_code, 403)
        self.assertIn('Administrators cannot impersonate either party', resp_supp.get_json()['error'])

    def test_duplicate_confirmation_rejected_with_409(self):
        """Attempting to submit a second confirmation for the same party role returns 409 Conflict."""
        self.login_user('nursery_amit')
        self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 150,
            'sound_qty': 145,
            'damaged_qty': 5
        })

        # Attempt duplicate Nursery confirmation
        resp_dup = self.client.post('/api/orders/ORD-8801/confirm', json={'party_role': 'NURSERY'})
        self.assertEqual(resp_dup.status_code, 409)
        self.assertIn('already confirmed', resp_dup.get_json()['error'])

    def test_mathematical_quantity_validations(self):
        """Server-side math validation rejects negative numbers, decimals, and sum mismatches."""
        self.login_user('nursery_amit')

        # Case A: Negative count
        resp_neg = self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 150,
            'sound_qty': -5,
            'damaged_qty': 155
        })
        self.assertEqual(resp_neg.status_code, 422)

        # Case B: Sum mismatch (140 + 5 != 150)
        resp_mismatch = self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 150,
            'sound_qty': 140,
            'damaged_qty': 5
        })
        self.assertEqual(resp_mismatch.status_code, 422)
        self.assertIn('Quantity calculation mismatch', resp_mismatch.get_json()['error'])

        # Case C: Non-integer / float
        resp_float = self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 150,
            'sound_qty': 145.5,
            'damaged_qty': 4.5
        })
        self.assertEqual(resp_float.status_code, 422)

        # Case D: Ordered vs Delivered discrepancy flagged without modifying original order
        resp_var = self.client.post('/api/orders/ORD-8801/inspection', json={
            'delivered_qty': 130, # 20 fewer than ordered (150)
            'sound_qty': 125,
            'damaged_qty': 5
        })
        self.assertEqual(resp_var.status_code, 200)
        data = resp_var.get_json()['data']
        # Original ordered_qty remains exactly 150
        self.assertEqual(data['order']['ordered_qty'], 150)
        self.assertEqual(data['inspection']['has_mismatch'], 1)
        self.assertEqual(data['inspection']['mismatch_diff'], -20)

    def test_direct_api_edits_after_locking_rejected(self):
        """
        ORD-8760 is seeded as pre-verified and locked.
        Direct API attempts to modify quantities must be rejected with 403 Forbidden.
        """
        self.login_user('nursery_amit')

        # Attempt to edit locked order ORD-8760
        resp_edit = self.client.post('/api/orders/ORD-8760/inspection', json={
            'delivered_qty': 100,
            'sound_qty': 100,
            'damaged_qty': 0
        })
        self.assertEqual(resp_edit.status_code, 403)
        self.assertIn('finalized and locked', resp_edit.get_json()['error'])

        # Verify data in database was NOT altered
        resp_check = self.client.get('/api/orders/ORD-8760')
        self.assertEqual(resp_check.status_code, 200)
        self.assertEqual(resp_check.get_json()['data']['inspection']['sound_qty'], 98)

    def test_direct_api_confirm_after_locking_rejected(self):
        """Attempting to counter-sign an already locked order returns 403 Forbidden."""
        self.login_user('supplier_rajesh')

        resp = self.client.post('/api/orders/ORD-8760/confirm', json={'party_role': 'SUPPLIER'})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('already permanently locked', resp.get_json()['error'])

    def test_localstorage_import_treated_as_untrusted_draft(self):
        """
        Imported client-side localStorage drafts must NEVER be marked as pre-verified or locked.
        They must be imported with is_locked = 0 and status = 'DRAFT'.
        """
        self.login_user('nursery_amit')

        resp = self.client.post('/api/inspections/import-local', json={
            'orderId': 'ORD-8802',
            'deliveredQty': 300,
            'soundQty': 295,
            'damagedQty': 5,
            'damageNotes': 'Client draft notes'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()['data']

        self.assertFalse(data['is_locked'])
        self.assertEqual(data['status'], 'DRAFT')
        self.assertFalse(data['nursery_confirmed'])
        self.assertFalse(data['supplier_confirmed'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
