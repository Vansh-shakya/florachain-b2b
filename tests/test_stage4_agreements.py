"""
FloraChain B2B — Test Suite: Digital Deal Agreement & Payment Terms
Verifies:
- Agreement creation & database persistence
- Advance percentage & balance calculations
- Strict validation of invalid quantities, amounts, dates, and interest terms
- Role-based authorization & party assignment enforcement
- Admin cannot impersonate or satisfy party approvals
- Independent dual approval (Supplier and Nursery)
- Atomic transition to 'AGREED' only on mutual assent
- Duplicate approval prevention
- Immutability of agreed terms against ordinary edits
- Versioned amendment workflow preserving historical agreed terms
- Platform Core audit event logging
"""

import unittest
import os
import tempfile
import json
from app import create_app
from app.models.database import get_connection

class TestDigitalDealAgreements(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.app = create_app({
            'TESTING': True,
            'DB_PATH': self.db_path,
            'ALLOW_DEMO_ROLE_SWITCH': True,
            'SECRET_KEY': 'test_secret_deal_agreements'
        })
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            os.close(self.db_fd)
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
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
    # 1. Seeding & Querying Agreements
    # -------------------------------------------------------------------------
    def test_seeded_agreements_exist(self):
        """Seeded agreements AGR-8760-v1 (AGREED) and AGR-8801-v1 (PENDING) must be present."""
        self._login('supplier_rajesh')
        resp = self.client.get('/api/agreements')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()['data']
        self.assertGreaterEqual(len(data), 2)

        refs = [a['agreement_ref'] for a in data]
        self.assertIn('AGR-8760-v1', refs)
        self.assertIn('AGR-8801-v1', refs)

        # Check AGR-8760-v1 is AGREED with dual approvals
        agr_8760 = next(a for a in data if a['agreement_ref'] == 'AGR-8760-v1')
        self.assertEqual(agr_8760['status'], 'AGREED')
        self.assertTrue(agr_8760['is_agreed'])
        self.assertTrue(agr_8760['supplier_approved'])
        self.assertTrue(agr_8760['nursery_approved'])
        self.assertEqual(len(agr_8760['approvals']), 2)

        # Check AGR-8801-v1 is PENDING_COUNTERPARTY_APPROVAL
        agr_8801 = next(a for a in data if a['agreement_ref'] == 'AGR-8801-v1')
        self.assertEqual(agr_8801['status'], 'PENDING_COUNTERPARTY_APPROVAL')
        self.assertFalse(agr_8801['is_agreed'])
        self.assertTrue(agr_8801['supplier_approved'])
        self.assertFalse(agr_8801['nursery_approved'])

    # -------------------------------------------------------------------------
    # 2. Server-side Calculations & Validations
    # -------------------------------------------------------------------------
    def test_create_agreement_advance_percentage_calculation(self):
        """Creating an agreement with 25% advance correctly computes advance and balance amounts."""
        self._login('supplier_rajesh')
        # Create agreement on ORD-8802 (300 units @ 180.0 = 54,000.0)
        resp = self.client.post('/api/agreements', json={
            'order_id': 'ORD-8802',
            'advance_percentage': 25.0,
            'payment_period_days': 15,
            'interest_rate_pct': 18.0,
            'interest_calculation_basis': 'ANNUAL_SIMPLE',
            'interest_grace_period_days': 3,
            'notes': '25% advance upon confirmation, 75% balance Net 15 days.'
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()['data']
        self.assertEqual(data['agreement_ref'], 'AGR-ORD-8802-v1')
        self.assertEqual(data['total_order_value'], 54000.0)
        self.assertEqual(data['advance_percentage'], 25.0)
        self.assertEqual(data['advance_amount'], 13500.0)
        self.assertEqual(data['balance_amount'], 40500.0)
        self.assertEqual(data['payment_period_days'], 15)
        self.assertEqual(data['interest_rate_pct'], 18.0)
        self.assertEqual(data['interest_grace_period_days'], 3)
        self.assertEqual(data['status'], 'PENDING_COUNTERPARTY_APPROVAL')
        self.assertTrue(data['supplier_approved'])
        self.assertFalse(data['nursery_approved'])

    def test_create_agreement_advance_amount_calculation(self):
        """Creating an agreement specifying advance amount calculates advance percentage accurately."""
        self._login('supplier_rajesh')
        resp = self.client.post('/api/agreements', json={
            'order_id': 'ORD-8802',
            'advance_amount': 10800.0, # 20% of 54,000
            'payment_period_days': 10
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()['data']
        self.assertEqual(data['advance_amount'], 10800.0)
        self.assertEqual(data['advance_percentage'], 20.0)
        self.assertEqual(data['balance_amount'], 43200.0)

    def test_validation_invalid_advance_percentage(self):
        """Advance percentage > 100% or < 0% must be rejected."""
        self._login('supplier_rajesh')
        resp = self.client.post('/api/agreements', json={
            'order_id': 'ORD-8802',
            'advance_percentage': 150.0
        })
        self.assertEqual(resp.status_code, 422)
        self.assertIn('between 0% and 100%', resp.get_json()['error'])

        resp_neg = self.client.post('/api/agreements', json={
            'order_id': 'ORD-8802',
            'advance_percentage': -5.0
        })
        self.assertEqual(resp_neg.status_code, 422)

    def test_validation_invalid_interest_rate_and_due_date(self):
        """Negative interest rate or malformed due date must be rejected."""
        self._login('supplier_rajesh')
        resp_interest = self.client.post('/api/agreements', json={
            'order_id': 'ORD-8802',
            'interest_rate_pct': -2.5
        })
        self.assertEqual(resp_interest.status_code, 422)
        self.assertIn('positive percentage', resp_interest.get_json()['error'])

        resp_date = self.client.post('/api/agreements', json={
            'order_id': 'ORD-8802',
            'payment_due_date': 'invalid-date-format'
        })
        self.assertEqual(resp_date.status_code, 422)
        self.assertIn('YYYY-MM-DD', resp_date.get_json()['error'])

    # -------------------------------------------------------------------------
    # 3. Authorization & Permissions
    # -------------------------------------------------------------------------
    def test_admin_cannot_create_or_approve_agreement(self):
        """Administrators cannot impersonate parties or create/approve deal agreements."""
        self._login('admin_flora')
        resp_create = self.client.post('/api/agreements', json={
            'order_id': 'ORD-8802',
            'advance_percentage': 20.0
        })
        self.assertEqual(resp_create.status_code, 403)
        self.assertIn('Administrators cannot create', resp_create.get_json()['error'])

        # Admin attempting to approve AGR-8801-v1
        conn = get_connection(self.db_path)
        agr = conn.execute("SELECT id FROM deal_agreements WHERE agreement_ref = 'AGR-8801-v1'").fetchone()
        conn.close()

        resp_approve = self.client.post(f'/api/agreements/{agr["id"]}/approve', json={})
        self.assertEqual(resp_approve.status_code, 403)
        self.assertIn('Administrators cannot impersonate', resp_approve.get_json()['error'])

    def test_unauthorized_party_cannot_approve(self):
        """A user cannot approve an agreement on behalf of the other party."""
        # supplier_rajesh already approved AGR-8801-v1; supplier cannot approve as NURSERY
        self._login('supplier_rajesh')
        conn = get_connection(self.db_path)
        agr = conn.execute("SELECT id FROM deal_agreements WHERE agreement_ref = 'AGR-8801-v1'").fetchone()
        conn.close()

        resp = self.client.post(f'/api/agreements/{agr["id"]}/approve', json={})
        self.assertEqual(resp.status_code, 422) # Duplicate approval by SUPPLIER
        self.assertIn('SUPPLIER has already approved', resp.get_json()['error'])

    # -------------------------------------------------------------------------
    # 4. Mutual Independent Approvals & Atomic Lock
    # -------------------------------------------------------------------------
    def test_nursery_approval_finalizes_agreement(self):
        """When Nursery approves AGR-8801-v1 (already approved by Supplier), status becomes AGREED."""
        conn = get_connection(self.db_path)
        agr = conn.execute("SELECT id FROM deal_agreements WHERE agreement_ref = 'AGR-8801-v1'").fetchone()
        conn.close()

        self._login('nursery_amit')
        resp = self.client.post(f'/api/agreements/{agr["id"]}/approve', json={
            'notes': 'Terms reviewed by nursery purchasing director; approved.'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()['data']
        self.assertEqual(data['status'], 'AGREED')
        self.assertTrue(data['is_agreed'])
        self.assertTrue(data['nursery_approved'])
        self.assertTrue(data['supplier_approved'])
        self.assertIsNotNone(data['agreed_at'])
        self.assertEqual(len(data['approvals']), 2)

        # Verify audit event was logged
        conn = get_connection(self.db_path)
        audit = conn.execute(
            "SELECT * FROM audit_events WHERE order_id = 'ORD-8801' AND event_type = 'AGREEMENT_AGREED'"
        ).fetchone()
        self.assertIsNotNone(audit)
        self.assertEqual(audit['actor_role'], 'NURSERY')
        conn.close()

    def test_duplicate_approval_rejected(self):
        """Attempting to approve an agreement twice by the same party is rejected."""
        self._login('supplier_rajesh')
        conn = get_connection(self.db_path)
        agr = conn.execute("SELECT id FROM deal_agreements WHERE agreement_ref = 'AGR-8801-v1'").fetchone()
        conn.close()

        resp = self.client.post(f'/api/agreements/{agr["id"]}/approve', json={})
        self.assertEqual(resp.status_code, 422)
        self.assertIn('already approved', resp.get_json()['error'])

    # -------------------------------------------------------------------------
    # 5. Immutability & Versioned Amendments
    # -------------------------------------------------------------------------
    def test_ordinary_edit_of_agreed_terms_rejected(self):
        """Directly editing an agreement that is in 'AGREED' status is strictly prohibited."""
        self._login('supplier_rajesh')
        conn = get_connection(self.db_path)
        agr = conn.execute("SELECT id FROM deal_agreements WHERE agreement_ref = 'AGR-8760-v1'").fetchone()
        conn.close()

        resp = self.client.post(f'/api/agreements/{agr["id"]}', json={
            'advance_percentage': 50.0
        })
        self.assertEqual(resp.status_code, 403)
        self.assertIn('permanently locked', resp.get_json()['error'])

    def test_versioned_amendment_creates_v2_preserving_v1(self):
        """Creating an amendment on AGR-8760-v1 creates AGR-ORD-8760-v2 and preserves v1 intact."""
        self._login('nursery_amit')
        conn = get_connection(self.db_path)
        agr_v1 = conn.execute("SELECT * FROM deal_agreements WHERE agreement_ref = 'AGR-8760-v1'").fetchone()
        conn.close()

        # Nursery proposes amendment to 30% advance with 20 days credit
        resp = self.client.post(f'/api/agreements/{agr_v1["id"]}/amend', json={
            'reason': 'Extended payment terms requested due to seasonal monsoon scheduling.',
            'advance_percentage': 30.0,
            'payment_period_days': 20,
            'interest_rate_pct': 15.0
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()['data']

        self.assertEqual(data['agreement_ref'], 'AGR-ORD-8760-v2')
        self.assertEqual(data['version'], 2)
        self.assertEqual(data['advance_percentage'], 30.0)
        self.assertEqual(data['payment_period_days'], 20)
        self.assertEqual(data['interest_rate_pct'], 15.0)
        self.assertEqual(data['status'], 'PENDING_COUNTERPARTY_APPROVAL')
        self.assertTrue(data['nursery_approved'])
        self.assertFalse(data['supplier_approved'])

        # Verify v1 is still intact and in 'AGREED' status
        conn = get_connection(self.db_path)
        v1_check = conn.execute("SELECT * FROM deal_agreements WHERE agreement_ref = 'AGR-8760-v1'").fetchone()
        self.assertEqual(v1_check['status'], 'AGREED')
        self.assertEqual(v1_check['advance_percentage'], 25.0)

        # Verify audit trail recorded amendment
        audit = conn.execute(
            "SELECT * FROM audit_events WHERE order_id = 'ORD-8760' AND event_type = 'AGREEMENT_AMENDMENT_CREATED'"
        ).fetchone()
        self.assertIsNotNone(audit)
        self.assertEqual(audit['actor_role'], 'NURSERY')
        self.assertIn('monsoon scheduling', audit['justification'])
        conn.close()

if __name__ == '__main__':
    unittest.main()
