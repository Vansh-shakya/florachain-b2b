"""
FloraChain B2B — Phase 14 Stage 2 Migration Utility Test Suite
Comprehensive testing of scripts/migrate_sqlite_to_postgres.py:
1. Default dry-run behavior (inspects source, emits plan, performs zero writes)
2. Confirmation guardrail (--confirm required to attempt writes)
3. Missing or invalid configuration handling (raises MigrationError)
4. Existing target data collision guardrail (aborts unless allow_existing=True)
5. Transaction rollback on transfer failure (atomic rollback, no partial writes)
6. Post-migration validation detection (catches row count and financial total discrepancies)
7. Source SQLite immutability (source database is opened read-only and never modified)
8. Sequence reset calculation for identity tables
"""

import unittest
import os
import sys
import tempfile
import sqlite3
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.models.database import init_database, get_connection
from scripts.migrate_sqlite_to_postgres import (
    run_migration,
    inspect_sqlite_database,
    check_target_cleanliness,
    copy_table_data,
    reset_identity_sequences,
    validate_migration,
    MigrationError,
    MigrationValidationError,
    TOPOLOGICAL_TABLE_ORDER
)


class TestPhase14MigrationUtility(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary source database
        self.src_fd, self.src_path = tempfile.mkstemp(suffix='.db')
        init_database(self.src_path)

    def tearDown(self):
        try:
            os.close(self.src_fd)
            if os.path.exists(self.src_path):
                os.unlink(self.src_path)
        except OSError:
            pass

    def test_01_dry_run_is_default_and_performs_zero_writes(self):
        """Dry-run mode is active by default and does not attempt any target writes."""
        # 1. Calling run_migration without confirm=True
        report = run_migration(
            sqlite_path=self.src_path,
            target_url="postgresql://user:pass@localhost:5432/mockdb",
            confirm=False,
            dry_run=True
        )

        self.assertEqual(report['mode'], 'DRY_RUN')
        self.assertIn('Dry-run inspection successful', report['message'])
        summary = report['summary']
        self.assertEqual(summary['counts']['users'], 3)
        self.assertEqual(summary['counts']['plants'], 6)
        self.assertEqual(summary['counts']['orders'], 3)
        self.assertEqual(summary['financials']['invoiced_gross'], 41160.0)
        self.assertEqual(summary['financials']['payments_recorded'], 10500.0)

    def test_02_source_sqlite_database_not_modified(self):
        """Source SQLite database remains strictly unmodified during inspection."""
        mtime_before = os.path.getmtime(self.src_path)
        size_before = os.path.getsize(self.src_path)

        run_migration(sqlite_path=self.src_path, confirm=False, dry_run=True)

        mtime_after = os.path.getmtime(self.src_path)
        size_after = os.path.getsize(self.src_path)

        self.assertEqual(mtime_before, mtime_after)
        self.assertEqual(size_before, size_after)

    def test_03_missing_or_invalid_source_path(self):
        """Missing SQLite source path immediately raises MigrationError."""
        with self.assertRaises(MigrationError) as ctx:
            run_migration(sqlite_path="nonexistent_path/fake.db", confirm=False, dry_run=True)
        self.assertIn("not found", str(ctx.exception).lower())

    def test_04_missing_or_invalid_target_url_on_confirmed_run(self):
        """Confirmed run without a valid target connection URL raises MigrationError."""
        with patch.dict(os.environ, {'TEST_DATABASE_URL': '', 'TARGET_DATABASE_URL': '', 'DATABASE_URL': '', 'PGPASSWORD': '', 'POSTGRES_PASSWORD': ''}, clear=False):
            with self.assertRaises(MigrationError) as ctx:
                run_migration(
                    sqlite_path=self.src_path,
                    target_url=None,
                    confirm=True,
                    dry_run=False
                )
            self.assertIn("target postgresql connection url is missing or invalid", str(ctx.exception).lower())

    def test_05_existing_target_data_collision_guardrail(self):
        """Aborts if target PostgreSQL database already contains data unless allow_existing=True."""
        mock_target = MagicMock()
        # Mock cleanliness check returning existing rows in 'users'
        mock_target.execute.return_value.fetchone.return_value = (5,)

        with self.assertRaises(MigrationError) as ctx:
            run_migration(
                sqlite_path=self.src_path,
                target_url="postgresql://mock:mock@localhost:5432/mockdb",
                confirm=True,
                dry_run=False,
                allow_existing=False,
                target_conn_override=mock_target
            )
        self.assertIn("already contains existing records", str(ctx.exception).lower())

    def test_06_atomic_transaction_rollback_on_failure(self):
        """Any error during data transfer triggers immediate target rollback."""
        mock_target = MagicMock()
        # Cleanliness check passes (0 rows)
        mock_target.execute.return_value.fetchone.return_value = (0,)

        # Simulate exception during executemany
        mock_target.executemany.side_effect = RuntimeError("Simulated network drop during copy")

        with self.assertRaises(RuntimeError):
            run_migration(
                sqlite_path=self.src_path,
                target_url="postgresql://mock:mock@localhost:5432/mockdb",
                confirm=True,
                dry_run=False,
                allow_existing=True,
                target_conn_override=mock_target
            )

        # Context manager __exit__ must have triggered rollback
        mock_target.__exit__.assert_called_once()
        args = mock_target.__exit__.call_args[0]
        self.assertIsNotNone(args[0], "Exception must be passed to __exit__ for rollback")

    def test_07_post_migration_validation_detects_mismatches(self):
        """validate_migration detects row count or financial discrepancy and raises MigrationValidationError."""
        conn_src = get_connection(self.src_path)

        # Mock target with mismatched row count on 'users' (2 instead of 3)
        mock_target = MagicMock()
        def mock_query(sql, *args):
            m = MagicMock()
            if "SELECT COUNT(*) FROM users" in sql:
                m.fetchone.return_value = (2,) # Mismatch!
            elif "SELECT COUNT(*)" in sql:
                m.fetchone.return_value = (3,)
            elif "SELECT id FROM users" in sql:
                m.fetchall.return_value = [(1,), (2,)] # Mismatch!
            elif "SELECT id FROM orders" in sql:
                m.fetchall.return_value = [('ORD-8760',), ('ORD-8801',), ('ORD-8802',)]
            elif "SELECT invoice_number" in sql:
                m.fetchall.return_value = [('INV-2026-8760',)]
            elif "SUM(total_amount)" in sql:
                m.fetchone.return_value = (41160.0,)
            elif "SUM(amount)" in sql:
                m.fetchone.return_value = (10500.0,)
            else:
                m.fetchone.return_value = (0,)
                m.fetchall.return_value = []
            return m

        mock_target.execute.side_effect = mock_query

        with self.assertRaises(MigrationValidationError) as ctx:
            validate_migration(conn_src, mock_target)
        self.assertIn("Row count mismatch on 'users'", str(ctx.exception))
        conn_src.close()

    def test_08_post_migration_validation_detects_financial_mismatches(self):
        """validate_migration catches discrepancies in financial invoiced gross or payments totals."""
        conn_src = get_connection(self.src_path)

        # Mock target where invoiced total is 40000.0 instead of 41160.0
        mock_target = MagicMock()
        def mock_query(sql, *args):
            m = MagicMock()
            if "SELECT COUNT(*)" in sql:
                # Return exact count from source
                table_name = sql.split("FROM ")[1].strip()
                count = conn_src.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                m.fetchone.return_value = (count,)
            elif "SELECT id FROM users" in sql:
                m.fetchall.return_value = [(1,), (2,), (3,)]
            elif "SELECT id FROM orders" in sql:
                m.fetchall.return_value = [('ORD-8760',), ('ORD-8801',), ('ORD-8802',)]
            elif "SELECT invoice_number" in sql:
                m.fetchall.return_value = [('INV-2026-8760',)]
            elif "SUM(total_amount)" in sql:
                m.fetchone.return_value = (40000.0,) # Financial mismatch!
            elif "SUM(amount)" in sql:
                m.fetchone.return_value = (10500.0,)
            else:
                m.fetchone.return_value = (0,)
                m.fetchall.return_value = []
            return m

        mock_target.execute.side_effect = mock_query

        with self.assertRaises(MigrationValidationError) as ctx:
            validate_migration(conn_src, mock_target)
        self.assertIn("Invoiced gross total mismatch", str(ctx.exception))
        conn_src.close()

    def test_09_sequence_resets_executed_for_identity_tables(self):
        """reset_identity_sequences generates setval queries for all autoincrement tables."""
        mock_target = MagicMock()
        mock_target.execute.return_value.fetchone.return_value = (10,)

        seq_res = reset_identity_sequences(mock_target)

        self.assertIn('users', seq_res)
        self.assertIn('plants', seq_res)
        self.assertIn('deal_agreements', seq_res)
        self.assertEqual(seq_res['users'], 10)
        # Verify setval was called for identity tables
        self.assertGreaterEqual(mock_target.execute.call_count, len(seq_res))


if __name__ == '__main__':
    unittest.main()

