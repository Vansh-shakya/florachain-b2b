"""
FloraChain B2B — Phase 14 Stage 3: Live PostgreSQL Validation Test Suite
Tests live connection, schema initialization, data migration from temp copy,
sequence advancement, adapter compatibility, and financial parity against florachain_test.
"""

import os
import sys
import shutil
import tempfile
import unittest
import datetime
from decimal import Decimal

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.models.database import (
    DEFAULT_DB_PATH,
    SCHEMA_POSTGRES_PATH,
    TABLES_WITH_AUTO_ID,
    get_connection,
    get_postgres_connection,
    is_postgres_url
)
from scripts.migrate_sqlite_to_postgres import (
    TOPOLOGICAL_TABLE_ORDER,
    resolve_target_url,
    mask_connection_url,
    run_migration,
    validate_migration,
    check_target_cleanliness,
    reset_identity_sequences
)


class TestStage14LivePostgresValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target_url = resolve_target_url()
        if not cls.target_url or not is_postgres_url(cls.target_url):
            raise unittest.SkipTest(
                "Live PostgreSQL connection URL is not configured. "
                "Set TEST_DATABASE_URL or PGPASSWORD to run live validation."
            )
        try:
            cls.test_conn = get_postgres_connection(cls.target_url)
        except Exception as e:
            raise unittest.SkipTest(f"Failed connecting to live PostgreSQL: {str(e)}")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'test_conn') and cls.test_conn:
            try:
                cls.test_conn.close()
            except Exception:
                pass

    def test_01_verify_connection_and_version(self):
        """Verifies real PostgreSQL server connection and version string."""
        cur = self.test_conn.execute("SELECT version();")
        row = cur.fetchone()
        self.assertIsNotNone(row)
        version_str = row[0]
        self.assertIn("PostgreSQL", version_str)
        print(f"\n[LIVE POSTGRES] Connected: {version_str.split(',')[0]}")

    def test_02_verify_target_is_dedicated_test_database(self):
        """Confirms that the connected database name is 'florachain_test'."""
        cur = self.test_conn.execute("SELECT current_database();")
        row = cur.fetchone()
        db_name = row[0]
        self.assertEqual(
            db_name.lower(),
            "florachain_test",
            f"Expected target to be 'florachain_test', got '{db_name}'. Aborting for safety."
        )

    def test_03_run_schema_and_migration_from_disposable_sqlite_copy(self):
        """
        Runs migration using a temporary copy of SQLite database into florachain_test.
        Verifies original florachain.db is never touched.
        """
        self.assertTrue(os.path.exists(DEFAULT_DB_PATH), "Source SQLite database must exist")
        orig_mtime = os.path.getmtime(DEFAULT_DB_PATH)
        orig_size = os.path.getsize(DEFAULT_DB_PATH)

        # Ensure target test database is clean before running migration
        with self.test_conn:
            self.test_conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        self.test_conn.commit()

        temp_dir = tempfile.mkdtemp(prefix="florachain_migration_test_")
        temp_sqlite_path = os.path.join(temp_dir, "temp_florachain.db")
        try:
            shutil.copy2(DEFAULT_DB_PATH, temp_sqlite_path)

            # Apply schema first to test database
            with open(SCHEMA_POSTGRES_PATH, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            with self.test_conn:
                self.test_conn.execute(schema_sql)
            self.test_conn.commit()

            # Run migration from temporary copy
            result = run_migration(
                sqlite_path=temp_sqlite_path,
                target_url=self.target_url,
                confirm=True,
                dry_run=False,
                allow_existing=True
            )
            self.assertEqual(result['status'], 'SUCCESS')
            self.assertEqual(result['mode'], 'CONFIRMED')
            self.assertEqual(result['summary']['total_rows'], 43)

            # Assert original SQLite database was untouched
            self.assertEqual(os.path.getmtime(DEFAULT_DB_PATH), orig_mtime)
            self.assertEqual(os.path.getsize(DEFAULT_DB_PATH), orig_size)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_04_validate_table_counts_and_primary_keys(self):
        """Validates dynamic row counts and primary keys for all 14 tables in PostgreSQL vs SQLite."""
        import sqlite3
        src_conn = sqlite3.connect(f"file:{os.path.abspath(DEFAULT_DB_PATH)}?mode=ro", uri=True)
        src_conn.row_factory = sqlite3.Row

        try:
            total_migrated = 0
            for table in TOPOLOGICAL_TABLE_ORDER:
                src_cnt = src_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                cur = self.test_conn.execute(f"SELECT COUNT(*) FROM {table}")
                tgt_cnt = cur.fetchone()[0]
                self.assertEqual(tgt_cnt, src_cnt, f"Count mismatch on table {table}: src={src_cnt}, tgt={tgt_cnt}")
                total_migrated += tgt_cnt
            self.assertEqual(total_migrated, 43)

            # Validate specific key entities
            src_users = {r[0] for r in src_conn.execute("SELECT id FROM users").fetchall()}
            tgt_users = {r[0] for r in self.test_conn.execute("SELECT id FROM users").fetchall()}
            self.assertEqual(src_users, tgt_users)

            src_orders = {r[0] for r in src_conn.execute("SELECT id FROM orders").fetchall()}
            tgt_orders = {r[0] for r in self.test_conn.execute("SELECT id FROM orders").fetchall()}
            self.assertEqual(src_orders, tgt_orders)

            src_invs = {r[0] for r in src_conn.execute("SELECT invoice_number FROM invoices").fetchall()}
            tgt_invs = {r[0] for r in self.test_conn.execute("SELECT invoice_number FROM invoices").fetchall()}
            self.assertEqual(src_invs, tgt_invs)

            src_payments = {r[0] for r in src_conn.execute("SELECT payment_number FROM payments").fetchall()}
            tgt_payments = {r[0] for r in self.test_conn.execute("SELECT payment_number FROM payments").fetchall()}
            self.assertEqual(src_payments, tgt_payments)

            src_agreements = {r[0] for r in src_conn.execute("SELECT agreement_ref FROM deal_agreements").fetchall()}
            tgt_agreements = {r[0] for r in self.test_conn.execute("SELECT agreement_ref FROM deal_agreements").fetchall()}
            self.assertEqual(src_agreements, tgt_agreements)
        finally:
            src_conn.close()

    def test_05_validate_financial_totals(self):
        """Validates exact financial parity in PostgreSQL against SQLite source."""
        import sqlite3
        src_conn = sqlite3.connect(f"file:{os.path.abspath(DEFAULT_DB_PATH)}?mode=ro", uri=True)
        try:
            # 1. Invoiced total
            src_invoiced = float(src_conn.execute(
                "SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE status = 'ISSUED'"
            ).fetchone()[0])
            cur = self.test_conn.execute(
                "SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE status = 'ISSUED'"
            )
            tgt_invoiced = float(cur.fetchone()[0])
            self.assertEqual(round(src_invoiced, 2), round(tgt_invoiced, 2))
            self.assertEqual(round(tgt_invoiced, 2), 41160.00)

            # 2. Payments total
            src_payments = float(src_conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'RECORDED'"
            ).fetchone()[0])
            cur = self.test_conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'RECORDED'"
            )
            tgt_payments = float(cur.fetchone()[0])
            self.assertEqual(round(src_payments, 2), round(tgt_payments, 2))
            self.assertEqual(round(tgt_payments, 2), 10500.00)

            # 3. Allocations total
            src_allocations = float(src_conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payment_allocations WHERE status = 'ACTIVE'"
            ).fetchone()[0])
            cur = self.test_conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payment_allocations WHERE status = 'ACTIVE'"
            )
            tgt_allocations = float(cur.fetchone()[0])
            self.assertEqual(round(src_allocations, 2), round(tgt_allocations, 2))
            self.assertEqual(round(tgt_allocations, 2), 10500.00)
        finally:
            src_conn.close()

    def test_06_verify_adapter_operations_and_sequence_advancement(self):
        """
        Verifies that PostgreSQL adapter handles INSERT with autoincrement ID generation,
        lastrowid mapping, and transaction rollback without primary key collisions.
        """
        # Test autoincrement insert
        insert_sql = """
            INSERT INTO plants (
                common_name, botanical_name, category, container_size, unit, unit_price, stock_qty, supplier_user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            "Live Validation Test Plant",
            "Ficus testii",
            "ORNAMENTAL",
            "10 inch Pot",
            "plant",
            199.50,
            50,
            1
        )
        cur = self.test_conn.execute(insert_sql, params)
        self.test_conn.commit()
        new_plant_id = cur.lastrowid
        self.assertIsNotNone(new_plant_id)
        self.assertGreater(new_plant_id, 6, "Generated plant ID should exceed migrated plant max ID 6")

        # Verify plant was inserted
        check_cur = self.test_conn.execute("SELECT * FROM plants WHERE id = ?", (new_plant_id,))
        row = check_cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['common_name'], "Live Validation Test Plant")
        self.assertEqual(float(row['unit_price']), 199.50)

        # Test transaction rollback
        try:
            with self.test_conn:
                self.test_conn.execute(
                    """INSERT INTO plants (
                        common_name, botanical_name, category, container_size, unit, unit_price, stock_qty, supplier_user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("Rollback Plant", "Ficus rb", "INDOOR", "6 inch", "plant", 99.00, 10, 1)
                )
                # Intentionally trigger an error
                raise RuntimeError("Controlled rollback test")
        except RuntimeError:
            pass

        # Verify rollbacked row does not exist
        rb_check = self.test_conn.execute("SELECT * FROM plants WHERE common_name = ?", ("Rollback Plant",))
        self.assertIsNone(rb_check.fetchone())

        # Cleanup the test plant
        with self.test_conn:
            self.test_conn.execute("DELETE FROM plants WHERE id = ?", (new_plant_id,))
        self.test_conn.commit()

        # Reset identity sequences back to pristine state
        reset_identity_sequences(self.test_conn)
        self.test_conn.commit()


if __name__ == '__main__':
    unittest.main()

