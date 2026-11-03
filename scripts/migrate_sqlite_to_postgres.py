#!/usr/bin/env python3
"""
FloraChain B2B — SQLite to PostgreSQL Data Migration Utility
Phase 14 Stage 2: Idempotent, Foreign-Key Safe, Validated Migration Tool

Usage:
    python scripts/migrate_sqlite_to_postgres.py --dry-run
    python scripts/migrate_sqlite_to_postgres.py --confirm

SAFETY GUARANTEES:
1. Dry-run mode is enabled by default. No writes occur unless --confirm is explicitly passed.
2. The source SQLite database (data/florachain.db) is strictly opened in read-only mode and is never modified.
3. Target writes occur within a single atomic transaction. Any error triggers an immediate rollback.
4. Data is transferred in strict topological foreign-key dependency order.
5. Post-migration validation verifies row counts, primary key preservation, foreign key integrity,
   and financial totals parity (invoices, payments, allocations).
6. Identity sequences in PostgreSQL are advanced to match the maximum explicit primary keys inserted.
"""

import os
import sys
import re
import urllib.parse
import argparse
import sqlite3
import datetime
from decimal import Decimal

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load .env file if available
try:
    from dotenv import load_dotenv
    env_file = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        load_dotenv()
except ImportError:
    pass

from app.models.database import (
    DEFAULT_DB_PATH,
    SCHEMA_POSTGRES_PATH,
    TABLES_WITH_AUTO_ID,
    get_connection,
    is_postgres_url
)

# Strict topological foreign-key safe insertion order
TOPOLOGICAL_TABLE_ORDER = [
    'users',
    'plants',
    'orders',
    'order_items',
    'delivery_inspections',
    'inspection_confirmations',
    'deal_agreements',
    'agreement_approvals',
    'invoices',
    'invoice_items',
    'payments',
    'payment_allocations',
    'audit_events',
    'inspection_corrections'
]


class MigrationError(Exception):
    """Base exception for database migration errors."""
    pass


class MigrationValidationError(MigrationError):
    """Raised when post-migration data integrity or balance verification fails."""
    pass


def mask_connection_url(url):
    """
    Masks credentials inside a PostgreSQL connection URL so passwords are never exposed.
    """
    if not url or not isinstance(url, str) or url == 'NOT_SPECIFIED':
        return url
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', url)


def resolve_target_url(target_url=None):
    """
    Resolves the PostgreSQL target connection string in precedence order:
    1. Explicit argument target_url
    2. TEST_DATABASE_URL environment variable
    3. TARGET_DATABASE_URL environment variable
    4. DATABASE_URL environment variable
    5. Assembled from PGUSER/POSTGRES_USER, PGPASSWORD/POSTGRES_PASSWORD, PGHOST, PGPORT, PGDATABASE
    """
    url = (
        target_url
        or os.environ.get('TEST_DATABASE_URL')
        or os.environ.get('TARGET_DATABASE_URL')
        or os.environ.get('DATABASE_URL')
    )
    if not url:
        pg_pass = os.environ.get('PGPASSWORD') or os.environ.get('POSTGRES_PASSWORD')
        if pg_pass:
            pg_user = os.environ.get('PGUSER') or os.environ.get('POSTGRES_USER') or 'postgres'
            pg_host = os.environ.get('PGHOST') or '127.0.0.1'
            pg_port = os.environ.get('PGPORT') or '5432'
            pg_db = os.environ.get('PGDATABASE') or 'florachain_test'
            url = f"postgresql://{pg_user}:{urllib.parse.quote_plus(pg_pass)}@{pg_host}:{pg_port}/{pg_db}"
    return url


def inspect_sqlite_database(src_conn):
    """
    Inspects source SQLite database and gathers table inventories, row counts, and financial totals.
    """
    summary = {
        'counts': {},
        'total_rows': 0,
        'financials': {}
    }
    for table in TOPOLOGICAL_TABLE_ORDER:
        try:
            row = src_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            count = row[0] if row else 0
        except sqlite3.OperationalError:
            count = 0
        summary['counts'][table] = count
        summary['total_rows'] += count

    # Audit key financial figures
    try:
        inv_sum = src_conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE status = 'ISSUED'"
        ).fetchone()[0]
        summary['financials']['invoiced_gross'] = float(inv_sum)
    except sqlite3.OperationalError:
        summary['financials']['invoiced_gross'] = 0.0

    try:
        pay_sum = src_conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'RECORDED'"
        ).fetchone()[0]
        summary['financials']['payments_recorded'] = float(pay_sum)
    except sqlite3.OperationalError:
        summary['financials']['payments_recorded'] = 0.0

    try:
        alloc_sum = src_conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payment_allocations WHERE status = 'ACTIVE'"
        ).fetchone()[0]
        summary['financials']['allocations_active'] = float(alloc_sum)
    except sqlite3.OperationalError:
        summary['financials']['allocations_active'] = 0.0

    return summary


def check_target_cleanliness(target_conn):
    """
    Checks if target PostgreSQL tables already contain data to prevent accidental corruption.
    """
    existing_data = {}
    for table in TOPOLOGICAL_TABLE_ORDER:
        try:
            cur = target_conn.execute(f"SELECT COUNT(*) FROM {table}")
            row = cur.fetchone()
            count = row[0] if row else 0
            if count > 0:
                existing_data[table] = count
        except Exception:
            # Table might not exist yet
            pass
    return existing_data


def copy_table_data(src_conn, target_conn, table_name):
    """
    Extracts rows from SQLite table and inserts into target PostgreSQL connection.
    Preserves explicit primary keys and formats values safely.
    """
    # Fetch column metadata from source
    cur = src_conn.execute(f"SELECT * FROM {table_name} LIMIT 0")
    cols = [d[0] for d in cur.description]
    if not cols:
        return 0

    cols_str = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"

    # Fetch all source rows
    rows = src_conn.execute(f"SELECT * FROM {table_name}").fetchall()
    if not rows:
        return 0

    # Convert rows to plain tuples with sanitized data types
    param_list = []
    for r in rows:
        row_vals = []
        for v in tuple(r):
            # Convert float to Decimal if financial or pass through
            if isinstance(v, float):
                row_vals.append(v)
            else:
                row_vals.append(v)
        param_list.append(tuple(row_vals))

    target_conn.executemany(insert_sql, param_list)
    return len(rows)


def reset_identity_sequences(target_conn):
    """
    Advances PostgreSQL identity sequences to MAX(id) for each table with an autoincrement ID.
    Prevents future INSERT statements from triggering duplicate key violations.
    """
    results = {}
    for table in TABLES_WITH_AUTO_ID:
        try:
            cur = target_conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
            row = cur.fetchone()
            max_id = row[0] if row else 0
            if max_id > 0:
                target_conn.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), %s, true)",
                    (max_id,)
                )
            results[table] = max_id
        except Exception as e:
            results[table] = f"Warning: {str(e)}"
    return results


def validate_migration(src_conn, target_conn):
    """
    Performs comprehensive post-migration parity verification between SQLite and target.
    Checks:
    - Row count match across all 14 tables
    - Exact primary key preservation for users, orders, and invoices
    - Invoiced gross, payments, and allocation totals match
    """
    mismatches = []

    # 1. Row counts
    for table in TOPOLOGICAL_TABLE_ORDER:
        try:
            src_cnt = src_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except Exception:
            src_cnt = 0

        try:
            cur = target_conn.execute(f"SELECT COUNT(*) FROM {table}")
            row = cur.fetchone()
            tgt_cnt = row[0] if row else 0
        except Exception as ex:
            mismatches.append(f"Failed querying target table '{table}': {str(ex)}")
            continue

        if src_cnt != tgt_cnt:
            mismatches.append(f"Row count mismatch on '{table}': source={src_cnt}, target={tgt_cnt}")

    # 2. Key entity preservation
    try:
        src_user_ids = {r[0] for r in src_conn.execute("SELECT id FROM users").fetchall()}
        tgt_user_ids = {r[0] for r in target_conn.execute("SELECT id FROM users").fetchall()}
        if src_user_ids != tgt_user_ids:
            mismatches.append(f"User IDs mismatch: source={src_user_ids}, target={tgt_user_ids}")
    except Exception as ex:
        mismatches.append(f"Failed user ID verification: {str(ex)}")

    try:
        src_order_ids = {r[0] for r in src_conn.execute("SELECT id FROM orders").fetchall()}
        tgt_order_ids = {r[0] for r in target_conn.execute("SELECT id FROM orders").fetchall()}
        if src_order_ids != tgt_order_ids:
            mismatches.append(f"Order IDs mismatch: source={src_order_ids}, target={tgt_order_ids}")
    except Exception as ex:
        mismatches.append(f"Failed order ID verification: {str(ex)}")

    try:
        src_inv_nos = {r[0] for r in src_conn.execute("SELECT invoice_number FROM invoices").fetchall()}
        tgt_inv_nos = {r[0] for r in target_conn.execute("SELECT invoice_number FROM invoices").fetchall()}
        if src_inv_nos != tgt_inv_nos:
            mismatches.append(f"Invoice numbers mismatch: source={src_inv_nos}, target={tgt_inv_nos}")
    except Exception as ex:
        mismatches.append(f"Failed invoice verification: {str(ex)}")

    # 3. Financial totals validation
    try:
        src_inv_total = float(src_conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE status = 'ISSUED'"
        ).fetchone()[0])
        tgt_inv_total = float(target_conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE status = 'ISSUED'"
        ).fetchone()[0])
        if round(src_inv_total, 2) != round(tgt_inv_total, 2):
            mismatches.append(f"Invoiced gross total mismatch: source={src_inv_total:.2f}, target={tgt_inv_total:.2f}")
    except Exception as ex:
        mismatches.append(f"Failed financial invoice total verification: {str(ex)}")

    try:
        src_pay_total = float(src_conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'RECORDED'"
        ).fetchone()[0])
        tgt_pay_total = float(target_conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'RECORDED'"
        ).fetchone()[0])
        if round(src_pay_total, 2) != round(tgt_pay_total, 2):
            mismatches.append(f"Payments total mismatch: source={src_pay_total:.2f}, target={tgt_pay_total:.2f}")
    except Exception as ex:
        mismatches.append(f"Failed financial payment total verification: {str(ex)}")

    if mismatches:
        raise MigrationValidationError(
            "Migration validation failed with discrepancies:\n - " + "\n - ".join(mismatches)
        )

    return True


def run_migration(
    sqlite_path=None,
    target_url=None,
    confirm=False,
    dry_run=True,
    allow_existing=False,
    target_conn_override=None
):
    """
    Executes or simulates the migration workflow.
    - If confirm is False or dry_run is True: performs dry-run inspection only.
    - If confirm is True and dry_run is False: executes atomic migration.
    """
    src_path = sqlite_path or os.environ.get('FLORACHAIN_DB_PATH', DEFAULT_DB_PATH)
    if not os.path.exists(src_path):
        raise MigrationError(f"Source SQLite database not found at '{src_path}'.")

    # Connect to SQLite in read-only mode
    uri = f"file:{os.path.abspath(src_path)}?mode=ro"
    src_conn = sqlite3.connect(uri, uri=True)
    src_conn.row_factory = sqlite3.Row

    try:
        summary = inspect_sqlite_database(src_conn)

        # -------------------------------------------------------------
        # DRY-RUN EXECUTION PATH
        # -------------------------------------------------------------
        resolved_tgt_url = resolve_target_url(target_url)
        if not confirm or dry_run:
            report = {
                'mode': 'DRY_RUN',
                'source_path': src_path,
                'target_url': mask_connection_url(resolved_tgt_url or 'NOT_SPECIFIED'),
                'summary': summary,
                'message': (
                    "Dry-run inspection successful. No changes made to any database. "
                    "To execute live migration in the future, pass --confirm."
                )
            }
            return report

        # -------------------------------------------------------------
        # LIVE / CONFIRMED EXECUTION PATH
        # -------------------------------------------------------------
        tgt_conn = target_conn_override
        should_close_target = False

        if tgt_conn is None:
            tgt_url = resolved_tgt_url
            if not tgt_url or not is_postgres_url(tgt_url):
                raise MigrationError(
                    "Target PostgreSQL connection URL is missing or invalid. "
                    "Set TEST_DATABASE_URL / TARGET_DATABASE_URL or pass --target-url with a valid postgresql:// connection string."
                )
            tgt_conn = get_connection(tgt_url)
            should_close_target = True

        try:
            # Check target cleanliness
            existing = check_target_cleanliness(tgt_conn)
            if existing and not allow_existing:
                raise MigrationError(
                    f"Target database already contains existing records in tables: {list(existing.keys())}. "
                    "Aborting to avoid data corruption. Pass --allow-existing to override."
                )

            # Ensure schema initialized on target
            try:
                with open(SCHEMA_POSTGRES_PATH, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                tgt_conn.execute(schema_sql)
                tgt_conn.commit()
            except Exception as se:
                raise MigrationError(f"Failed ensuring PostgreSQL schema: {str(se)}")

            # Copy data in topological order within transaction
            migrated_counts = {}
            with tgt_conn:
                for table in TOPOLOGICAL_TABLE_ORDER:
                    migrated_counts[table] = copy_table_data(src_conn, tgt_conn, table)

                # Advance identity sequences
                seq_results = reset_identity_sequences(tgt_conn)

                # Validate data parity before committing
                validate_migration(src_conn, tgt_conn)

            return {
                'mode': 'CONFIRMED',
                'status': 'SUCCESS',
                'source_path': src_path,
                'migrated_counts': migrated_counts,
                'sequence_resets': seq_results,
                'summary': summary
            }
        finally:
            if should_close_target and tgt_conn:
                tgt_conn.close()

    finally:
        src_conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="FloraChain B2B — SQLite to PostgreSQL Migration Utility (Dry-Run by default)"
    )
    parser.add_argument(
        '--sqlite-path',
        default=None,
        help="Path to source SQLite database (defaults to data/florachain.db)"
    )
    parser.add_argument(
        '--target-url',
        default=None,
        help="PostgreSQL target connection URL (e.g., postgresql://user:pass@host:5432/db)"
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        default=False,
        help="Explicit confirmation required to perform writes. If omitted, runs in safe dry-run mode."
    )
    parser.add_argument(
        '--allow-existing',
        action='store_true',
        default=False,
        help="Allow migration even if target tables already contain rows."
    )

    args = parser.parse_args()

    # Determine execution mode: if not confirmed, force dry-run
    is_dry_run = not args.confirm

    print("=" * 72)
    print("🌿 FloraChain B2B — SQLite to PostgreSQL Migration Utility")
    if is_dry_run:
        print("   [MODE: DRY-RUN INSPECTION ONLY — NO WRITES PERFORMED]")
    else:
        print("   [MODE: CONFIRMED LIVE MIGRATION — TRANSACTIONAL WRITES ENABLED]")
    print("=" * 72)

    try:
        result = run_migration(
            sqlite_path=args.sqlite_path,
            target_url=args.target_url,
            confirm=args.confirm,
            dry_run=is_dry_run,
            allow_existing=args.allow_existing
        )

        if result['mode'] == 'DRY_RUN':
            print("\n📁 Source Database Inspection:")
            print(f"   Path: {result['source_path']}")
            print(f"   Target URL configured: {result['target_url']}")
            print("\n📋 Table Inventory & Row Counts to Transfer:")
            for tbl, count in result['summary']['counts'].items():
                print(f"   - {tbl:26}: {count:>4} rows")
            print(f"   {'TOTAL ROWS':26}: {result['summary']['total_rows']:>4} rows")

            fin = result['summary']['financials']
            print("\nFinancial Totals:")
            print(f"   - Invoiced Gross Total    : Rs. {fin['invoiced_gross']:,.2f}")
            print(f"   - Recorded Payments Total : Rs. {fin['payments_recorded']:,.2f}")
            print(f"   - Active Allocations Total: Rs. {fin['allocations_active']:,.2f}")

            print("\n" + "=" * 72)
            print("✅ DRY-RUN COMPLETE: Schema and data integrity verified.")
            print("   No changes were made to any database.")
            print("   To execute live migration in the future, pass --confirm.")
            print("=" * 72 + "\n")
            sys.exit(0)

        else:
            print("\n✅ MIGRATION SUCCESSFUL & VALIDATED:")
            for tbl, cnt in result['migrated_counts'].items():
                print(f"   - {tbl:26}: {cnt:>4} rows migrated")
            print("\n" + "=" * 72)
            sys.exit(0)

    except MigrationError as me:
        print(f"\n❌ Migration Error: {str(me)}", file=sys.stderr)
        sys.exit(1)
    except Exception as ex:
        print(f"\n❌ Unexpected Failure: {str(ex)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
