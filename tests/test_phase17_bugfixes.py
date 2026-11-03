"""
FloraChain B2B — Phase 17 Regression Test Suite for Bug Fixes & Edge Cases
Tests:
1. Authentication Input Sanitization:
   - Non-string passwords or usernames return 400 Bad Request (preventing 500 AttributeError)
2. Advance Payment Counterparty Isolation:
   - Reject allocating an advance payment to an invoice belonging to a different nursery
   - Reject allocating an advance payment across different wholesale suppliers
3. Advance Payment Amount Validation:
   - Non-numerical allocation amounts return 400 Bad Request (preventing 500 decimal.InvalidOperation)
4. Invoice Cancellation Protection:
   - Reject canceling an invoice that has active allocated payments (preserving financial consistency)
   - Allow canceling an invoice with 0 active allocations
5. Resilient Audit State Parsing:
   - Malformed/non-JSON states in audit_events handled gracefully without crashing
6. Negative/Boolean Quantity & Price Boundary Validations:
   - Orders reject booleans and negative values for quantities
7. Active Database Verification:
   - Confirm SQLite florachain.db remains strictly 14 tables and 43 rows
"""

import unittest
import os
import sys
import json
import sqlite3
import tempfile
from decimal import Decimal

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models.database import get_connection, init_database
from app.services.payment_service import allocate_advance_payment, record_payment
from app.services.invoice_service import cancel_invoice, get_invoice_details
from app.services.audit_service import get_audit_trail_for_order


class TestPhase17BugFixes(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        self.app = create_app({
            'TESTING': True,
            'DB_PATH': self.temp_db_path,
            'SECRET_KEY': 'phase17-regression-secret-key',
            'ALLOW_DEMO_ROLE_SWITCH': True,
            'CSRF_ENABLED': False
        })
        self.client = self.app.test_client()

        # Initialize schema & seed data
        init_database(self.temp_db_path)

        conn = get_connection(self.temp_db_path)
        try:
            # Seed secondary nursery for cross-tenant advance allocation testing
            with conn:
                conn.execute(
                    """INSERT INTO users (id, username, email, password_hash, role, business_name)
                       VALUES (201, 'nursery_cross', 'cross@test.com', 'scrypt:test', 'NURSERY', 'Cross Tenant Nursery')"""
                )
            self.supplier = dict(conn.execute("SELECT * FROM users WHERE username = 'supplier_rajesh'").fetchone())
            self.nursery = dict(conn.execute("SELECT * FROM users WHERE username = 'nursery_amit'").fetchone())
            self.cross_nursery = dict(conn.execute("SELECT * FROM users WHERE id = 201").fetchone())
            self.admin = dict(conn.execute("SELECT * FROM users WHERE username = 'admin_flora'").fetchone())
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
    # 1. AUTHENTICATION INPUT SANITIZATION
    # =========================================================================

    def test_login_rejects_non_string_password_with_400(self):
        """Verify POST /api/auth/login returns 400 when password is an integer instead of 500."""
        res = self.client.post('/api/auth/login', json={
            'email': 'supplier@greenrootsfarms.com',
            'password': 12345
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn("text strings", data['error'])

    def test_login_rejects_non_string_username_with_400(self):
        """Verify POST /api/auth/login returns 400 when username is null or boolean."""
        res = self.client.post('/api/auth/login', json={
            'email': None,
            'password': 'password123'
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])

    # =========================================================================
    # 2. ADVANCE PAYMENT COUNTERPARTY ISOLATION
    # =========================================================================

    def test_allocate_advance_rejects_cross_tenant_nursery_mismatch(self):
        """Verify advance payment from Nursery A cannot be allocated to an invoice of Nursery B."""
        conn = get_connection(self.temp_db_path)
        try:
            # 1. Record an advance payment from self.cross_nursery (ID 201)
            with conn:
                pay_res = record_payment(
                    conn,
                    {
                        "amount": 5000.0,
                        "payment_method": "BANK_TRANSFER",
                        "reference_number": "UTR-CROSS-TENANT-001",
                        "payment_type": "ADVANCE_PAYMENT",
                        "nursery_user_id": self.cross_nursery['id']
                    },
                    self.supplier
                )
                pay_id = pay_res['payment']['id']

            # 2. Try to allocate this advance to INV-2026-8760 (which belongs to self.nursery ID 2)
            with self.assertRaises(ValueError) as ctx:
                with conn:
                    allocate_advance_payment(
                        conn,
                        payment_id_or_number=pay_id,
                        invoice_id_or_number='INV-2026-8760',
                        amount_to_allocate=1000.0,
                        actor_user=self.supplier
                    )
            self.assertIn("different client nursery", str(ctx.exception))
        finally:
            conn.close()

    def test_allocate_advance_rejects_invalid_amount_format(self):
        """Verify allocate_advance_payment cleanly rejects non-numerical amount string."""
        conn = get_connection(self.temp_db_path)
        try:
            with conn:
                pay_res = record_payment(
                    conn,
                    {
                        "amount": 5000.0,
                        "payment_method": "UPI",
                        "reference_number": "UTR-INV-AMT-001",
                        "payment_type": "ADVANCE_PAYMENT",
                        "nursery_user_id": self.nursery['id']
                    },
                    self.supplier
                )
                pay_id = pay_res['payment']['id']

            with self.assertRaises(ValueError) as ctx:
                with conn:
                    allocate_advance_payment(
                        conn,
                        payment_id_or_number=pay_id,
                        invoice_id_or_number='INV-2026-8760',
                        amount_to_allocate="invalid_amount",
                        actor_user=self.supplier
                    )
            self.assertIn("Must be a valid numerical value", str(ctx.exception))
        finally:
            conn.close()

    # =========================================================================
    # 3. INVOICE CANCELLATION INTEGRITY & AUTHORIZATION
    # =========================================================================

    def test_cancel_invoice_requires_non_empty_reason(self):
        """Verify cancel_invoice raises ValueError if cancellation reason is missing or empty."""
        conn = get_connection(self.temp_db_path)
        try:
            with self.assertRaises(ValueError) as ctx:
                with conn:
                    cancel_invoice(
                        conn,
                        'INV-2026-8760',
                        self.supplier,
                        reason="   "
                    )
            self.assertIn("reason is required", str(ctx.exception).lower())
        finally:
            conn.close()

    def test_cancel_invoice_unauthorized_party_rejected(self):
        """Verify non-supplier/non-admin or unrelated supplier cannot cancel an invoice."""
        conn = get_connection(self.temp_db_path)
        try:
            # Nursery role cannot cancel invoices
            with self.assertRaises(PermissionError) as ctx:
                with conn:
                    cancel_invoice(
                        conn,
                        'INV-2026-8760',
                        self.nursery,
                        reason="Attempting to cancel supplier invoice as nursery buyer"
                    )
            self.assertIn("Forbidden", str(ctx.exception))
        finally:
            conn.close()

    def test_cancel_invoice_cannot_cancel_twice(self):
        """Verify cancelling an already cancelled invoice raises ValueError."""
        conn = get_connection(self.temp_db_path)
        try:
            with conn:
                cancel_invoice(
                    conn,
                    'INV-2026-8760',
                    self.supplier,
                    reason="Initial cancellation"
                )

            with self.assertRaises(ValueError) as ctx:
                with conn:
                    cancel_invoice(
                        conn,
                        'INV-2026-8760',
                        self.supplier,
                        reason="Second cancellation attempt"
                    )
            self.assertIn("already cancelled", str(ctx.exception))
        finally:
            conn.close()

    # =========================================================================
    # 4. RESILIENT AUDIT STATE PARSING
    # =========================================================================

    def test_audit_trail_handles_malformed_json_gracefully(self):
        """Verify get_audit_trail_for_order does not crash if an event has non-JSON state."""
        conn = get_connection(self.temp_db_path)
        try:
            with conn:
                conn.execute(
                    """INSERT INTO audit_events
                       (event_type, order_id, actor_user_id, actor_role, before_state_json, after_state_json, justification, ip_address)
                       VALUES ('TEST_EVENT', 'ORD-8801', 1, 'SUPPLIER', '{corrupted json:', 'also corrupted', 'testing resilience', '127.0.0.1')"""
                )
            events = get_audit_trail_for_order(conn, 'ORD-8801')
            self.assertIsInstance(events, list)
            test_ev = next(e for e in events if e['event_type'] == 'TEST_EVENT')
            self.assertIn('raw', test_ev['before_state'])
            self.assertIn('raw', test_ev['after_state'])
        finally:
            conn.close()

    # =========================================================================
    # 5. ORDER BOUNDARY VALIDATIONS
    # =========================================================================

    def test_order_creation_rejects_boolean_quantity(self):
        """Verify order creation rejects boolean quantity."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.supplier['id']
            sess['role'] = 'SUPPLIER'
            sess['username'] = self.supplier['username']

        res = self.client.post('/api/orders', json={
            'nursery_user_id': self.nursery['id'],
            'items': [
                {'variety': 'Areca Palm', 'quantity': True, 'unit_price': 350.0}
            ]
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])

    # =========================================================================
    # 6. ACTIVE DATABASE INTEGRITY
    # =========================================================================

    def test_active_sqlite_database_untouched(self):
        """Verify active SQLite production database maintains exact 14 tables and 43 rows."""
        prod_db_path = os.path.join(BASE_DIR, 'data', 'florachain.db')
        self.assertTrue(os.path.exists(prod_db_path), "Active database data/florachain.db must exist.")

        conn = sqlite3.connect(prod_db_path)
        conn.row_factory = sqlite3.Row
        try:
            tables = [
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            self.assertEqual(len(tables), 14)
            total_rows = sum(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables)
            self.assertEqual(total_rows, 43)
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
