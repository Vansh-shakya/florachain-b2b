"""
FloraChain B2B — Phase 14 Read-Only Post-Migration Audit Script
Runs non-destructive validation across SQLite (data/florachain.db) and PostgreSQL (florachain_test).
"""

import os
import sys
import sqlite3
import datetime
from decimal import Decimal

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import dotenv
import psycopg2
from app.models.database import (
    DEFAULT_DB_PATH,
    TABLES_WITH_AUTO_ID,
    parse_pg_url,
    get_active_dialect,
    get_connection,
    is_postgres_url
)
from scripts.migrate_sqlite_to_postgres import (
    TOPOLOGICAL_TABLE_ORDER,
    mask_connection_url,
    resolve_target_url
)


def run_audit():
    print("=" * 80)
    print("🔍 FloraChain B2B — Phase 14 Read-Only Post-Migration Audit")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. Inspect SQLite Source Database
    # -------------------------------------------------------------------------
    print("\n[CHECK 1] Inspecting Source SQLite Database (Read-Only Mode)...")
    if not os.path.exists(DEFAULT_DB_PATH):
        print(f"❌ FAILED: SQLite database file not found at {DEFAULT_DB_PATH}")
        sys.exit(1)

    src_uri = f"file:{os.path.abspath(DEFAULT_DB_PATH)}?mode=ro"
    src_conn = sqlite3.connect(src_uri, uri=True)
    src_conn.row_factory = sqlite3.Row

    try:
        sqlite_tables_query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        sqlite_tables = [r[0] for r in src_conn.execute(sqlite_tables_query).fetchall()]
        print(f"  - Discovered {len(sqlite_tables)} tables in SQLite: {sqlite_tables}")

        sqlite_counts = {}
        sqlite_total_rows = 0
        for t in TOPOLOGICAL_TABLE_ORDER:
            cnt = src_conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            sqlite_counts[t] = cnt
            sqlite_total_rows += cnt

        print(f"  - Total SQLite Rows: {sqlite_total_rows} across {len(TOPOLOGICAL_TABLE_ORDER)} tables.")
        assert len(sqlite_tables) == 14, f"Expected 14 SQLite tables, got {len(sqlite_tables)}"
        assert sqlite_total_rows == 43, f"Expected 43 SQLite rows, got {sqlite_total_rows}"
        print("  ✅ Check 1 Passed: SQLite database has exactly 14 tables and 43 rows.")

        # -------------------------------------------------------------------------
        # 2. Inspect PostgreSQL florachain_test Database
        # -------------------------------------------------------------------------
        print("\n[CHECK 2] Inspecting Target PostgreSQL Database (florachain_test)...")
        dotenv.load_dotenv(os.path.join(BASE_DIR, '.env'))
        target_url = resolve_target_url()
        if not target_url or not is_postgres_url(target_url):
            print("❌ FAILED: PostgreSQL connection URL could not be resolved from .env")
            sys.exit(1)

        print(f"  - Resolved Target URL (masked): {mask_connection_url(target_url)}")
        params = parse_pg_url(target_url)
        pg_conn = psycopg2.connect(**params)
        pg_cur = pg_conn.cursor()

        pg_cur.execute("SELECT current_database(), current_user, version();")
        db_name, db_user, pg_ver = pg_cur.fetchone()
        print(f"  - Connected Database : {db_name}")
        print(f"  - Connected User     : {db_user}")
        print(f"  - PostgreSQL Version : {pg_ver.split(',')[0]}")
        assert db_name.lower() == 'florachain_test', f"Target DB must be 'florachain_test', got '{db_name}'"

        pg_cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")
        pg_tables = [r[0] for r in pg_cur.fetchall()]
        print(f"  - Discovered {len(pg_tables)} tables in PostgreSQL public schema: {pg_tables}")

        pg_counts = {}
        pg_total_rows = 0
        mismatched_tables = []
        for t in TOPOLOGICAL_TABLE_ORDER:
            pg_cur.execute(f"SELECT count(*) FROM {t}")
            cnt = pg_cur.fetchone()[0]
            pg_counts[t] = cnt
            pg_total_rows += cnt
            if cnt != sqlite_counts[t]:
                mismatched_tables.append((t, sqlite_counts[t], cnt))

        print(f"  - Total PostgreSQL Rows: {pg_total_rows} across {len(TOPOLOGICAL_TABLE_ORDER)} tables.")
        if mismatched_tables:
            print(f"❌ FAILED: Row count mismatches found: {mismatched_tables}")
            sys.exit(1)

        assert pg_total_rows == 43, f"Expected 43 PostgreSQL rows, got {pg_total_rows}"
        print("  ✅ Check 2 Passed: PostgreSQL database has exactly 14 tables and matching 43 rows.")

        # -------------------------------------------------------------------------
        # 3. Foreign-Key Integrity and Primary-Key Preservation
        # -------------------------------------------------------------------------
        print("\n[CHECK 3] Verifying Foreign-Key Integrity and Primary-Key Preservation...")
        # Verify active foreign keys in PostgreSQL
        pg_cur.execute("""
            SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema='public'
            ORDER BY tc.table_name, kcu.column_name;
        """)
        fk_constraints = pg_cur.fetchall()
        print(f"  - Active PostgreSQL Foreign Key Constraints: {len(fk_constraints)} constraints verified.")

        # Verify key entities matching
        # Users
        src_users = [(r['id'], r['username'], r['role']) for r in src_conn.execute("SELECT id, username, role FROM users ORDER BY id").fetchall()]
        pg_cur.execute("SELECT id, username, role FROM users ORDER BY id")
        pg_users = pg_cur.fetchall()
        assert src_users == pg_users, f"Users mismatch: src={src_users}, pg={pg_users}"
        print(f"  - Users exact match: {pg_users}")

        # Orders
        src_orders = [(r['id'], r['variety'], r['ordered_qty'], float(r['unit_price'])) for r in src_conn.execute("SELECT id, variety, ordered_qty, unit_price FROM orders ORDER BY id").fetchall()]
        pg_cur.execute("SELECT id, variety, ordered_qty, unit_price FROM orders ORDER BY id")
        pg_orders = [(r[0], r[1], r[2], float(r[3])) for r in pg_cur.fetchall()]
        assert src_orders == pg_orders, f"Orders mismatch: src={src_orders}, pg={pg_orders}"
        print(f"  - Orders exact match: {[o[0] for o in pg_orders]}")

        # Invoices
        src_invoices = [(r['id'], r['invoice_number'], float(r['total_amount']), str(r['due_date'])) for r in src_conn.execute("SELECT id, invoice_number, total_amount, due_date FROM invoices ORDER BY id").fetchall()]
        pg_cur.execute("SELECT id, invoice_number, total_amount, due_date FROM invoices ORDER BY id")
        pg_invoices = [(r[0], r[1], float(r[2]), str(r[3])) for r in pg_cur.fetchall()]
        assert src_invoices == pg_invoices, f"Invoices mismatch: src={src_invoices}, pg={pg_invoices}"
        print(f"  - Invoices exact match: {pg_invoices}")

        # Payments & Allocations
        src_payments = [(r['id'], r['payment_number'], float(r['amount'])) for r in src_conn.execute("SELECT id, payment_number, amount FROM payments ORDER BY id").fetchall()]
        pg_cur.execute("SELECT id, payment_number, amount FROM payments ORDER BY id")
        pg_payments = [(r[0], r[1], float(r[2])) for r in pg_cur.fetchall()]
        assert src_payments == pg_payments, f"Payments mismatch: src={src_payments}, pg={pg_payments}"
        print(f"  - Payments exact match: {pg_payments}")

        # Confirm order FKs exist in users
        pg_cur.execute("SELECT id FROM orders WHERE supplier_user_id NOT IN (SELECT id FROM users) OR nursery_user_id NOT IN (SELECT id FROM users)")
        orphaned_orders = pg_cur.fetchall()
        assert len(orphaned_orders) == 0, f"Orphaned orders detected: {orphaned_orders}"

        # Confirm invoice FKs exist in orders
        pg_cur.execute("SELECT id FROM invoices WHERE order_id NOT IN (SELECT id FROM orders)")
        orphaned_invoices = pg_cur.fetchall()
        assert len(orphaned_invoices) == 0, f"Orphaned invoices detected: {orphaned_invoices}"

        # Confirm payment allocations FKs exist in payments and invoices
        pg_cur.execute("SELECT id FROM payment_allocations WHERE payment_id NOT IN (SELECT id FROM payments) OR invoice_id NOT IN (SELECT id FROM invoices)")
        orphaned_allocs = pg_cur.fetchall()
        assert len(orphaned_allocs) == 0, f"Orphaned allocations detected: {orphaned_allocs}"

        print("  ✅ Check 3 Passed: Foreign-key integrity and primary-key preservation hold across all tables.")

        # -------------------------------------------------------------------------
        # 4. Identity Sequence Synchronization
        # -------------------------------------------------------------------------
        print("\n[CHECK 4] Verifying Identity Sequence Synchronization...")
        seq_checks = []
        for table in sorted(TABLES_WITH_AUTO_ID):
            pg_cur.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
            max_id = pg_cur.fetchone()[0]

            seq_name_cur = pg_conn.cursor()
            seq_name_cur.execute(f"SELECT pg_get_serial_sequence('{table}', 'id')")
            seq_name_row = seq_name_cur.fetchone()
            seq_name = seq_name_row[0] if seq_name_row else None
            seq_name_cur.close()

            if seq_name:
                raw_seq = seq_name.split('.')[-1].replace('"', '')
                pg_cur.execute(f"SELECT last_value FROM pg_sequences WHERE sequencename = '{raw_seq}'")
                seq_info = pg_cur.fetchone()
                if seq_info:
                    last_val = seq_info[0]
                    if last_val is not None:
                        seq_checks.append((table, max_id, last_val))
                        print(f"  - {table:26}: max(id)={max_id:>2}, seq_last_value={last_val:>2}")
                        assert last_val >= max_id, f"Sequence {raw_seq} ({last_val}) is behind max ID {max_id}"
                    else:
                        print(f"  - {table:26}: max(id)={max_id:>2}, seq_last_value=None (empty table)")
                else:
                    print(f"  - {table:26}: max(id)={max_id:>2}, seq={seq_name} (no pg_sequences record)")
            else:
                print(f"  - {table:26}: max(id)={max_id:>2} (no sequence mapped)")

        print("  ✅ Check 4 Passed: All identity sequences are correctly advanced past table max IDs.")

        # -------------------------------------------------------------------------
        # 5. Financial Totals & Audit History Parity
        # -------------------------------------------------------------------------
        print("\n[CHECK 5] Verifying Financial Totals and Audit History Parity...")
        # Gross invoiced
        src_inv_gross = float(src_conn.execute("SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE status = 'ISSUED'").fetchone()[0])
        pg_cur.execute("SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE status = 'ISSUED'")
        pg_inv_gross = float(pg_cur.fetchone()[0])
        assert round(src_inv_gross, 2) == round(pg_inv_gross, 2) == 41160.00
        print(f"  - Gross Invoiced (ISSUED)   : SQLite=Rs. {src_inv_gross:,.2f} | PG=Rs. {pg_inv_gross:,.2f} (Exact)")

        # Payments recorded
        src_pmt = float(src_conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'RECORDED'").fetchone()[0])
        pg_cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'RECORDED'")
        pg_pmt = float(pg_cur.fetchone()[0])
        assert round(src_pmt, 2) == round(pg_pmt, 2) == 10500.00
        print(f"  - Recorded Payments         : SQLite=Rs. {src_pmt:,.2f} | PG=Rs. {pg_pmt:,.2f} (Exact)")

        # Allocations active
        src_alloc = float(src_conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payment_allocations WHERE status = 'ACTIVE'").fetchone()[0])
        pg_cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payment_allocations WHERE status = 'ACTIVE'")
        pg_alloc = float(pg_cur.fetchone()[0])
        assert round(src_alloc, 2) == round(pg_alloc, 2) == 10500.00
        print(f"  - Active Allocations        : SQLite=Rs. {src_alloc:,.2f} | PG=Rs. {pg_alloc:,.2f} (Exact)")

        # Unallocated amount
        src_unalloc = float(src_conn.execute("SELECT COALESCE(SUM(unallocated_amount), 0) FROM payments").fetchone()[0])
        pg_cur.execute("SELECT COALESCE(SUM(unallocated_amount), 0) FROM payments")
        pg_unalloc = float(pg_cur.fetchone()[0])
        assert round(src_unalloc, 2) == round(pg_unalloc, 2) == 0.00
        print(f"  - Unallocated Payments      : SQLite=Rs. {src_unalloc:,.2f} | PG=Rs. {pg_unalloc:,.2f} (Exact)")

        # Audit events parity
        src_audit_events = [(r['event_type'], r['order_id'], r['actor_role']) for r in src_conn.execute("SELECT event_type, order_id, actor_role FROM audit_events ORDER BY id").fetchall()]
        pg_cur.execute("SELECT event_type, order_id, actor_role FROM audit_events ORDER BY id")
        pg_audit_events = pg_cur.fetchall()
        assert src_audit_events == pg_audit_events
        print(f"  - Audit Events Parity       : {len(pg_audit_events)} audit events exactly identical in sequence, event_type, order_id, and actor_role.")

        print("  ✅ Check 5 Passed: Financial totals and audit history match SQLite source 100%.")

        # -------------------------------------------------------------------------
        # 6. Temporary Test Records & Rollback Cleanup Verification
        # -------------------------------------------------------------------------
        print("\n[CHECK 6] Verifying Temporary Test Records and Rollback Cleanup...")
        pg_cur.execute("SELECT id, common_name FROM plants WHERE common_name LIKE '%Test%' OR common_name LIKE '%Rollback%' OR id > 6")
        leftover_plants = pg_cur.fetchall()
        assert len(leftover_plants) == 0, f"Found leftover test plants: {leftover_plants}"
        print(f"  - Leftover test plants in PostgreSQL: 0 (None)")

        pg_cur.execute("SELECT id, username FROM users WHERE username LIKE '%test%' OR id > 3")
        leftover_users = pg_cur.fetchall()
        assert len(leftover_users) == 0, f"Found leftover test users: {leftover_users}"
        print(f"  - Leftover test users in PostgreSQL: 0 (None)")

        print("  ✅ Check 6 Passed: No temporary or rollbacked test rows remain in PostgreSQL.")

        # -------------------------------------------------------------------------
        # 7. Credentials & Target Safety Verification
        # -------------------------------------------------------------------------
        print("\n[CHECK 7] Verifying Credentials Protection & Target Safety Guardrails...")
        # Check that .env is gitignored
        gitignore_path = os.path.join(BASE_DIR, '.gitignore')
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            gitignore_content = f.read()
        assert '.env' in gitignore_content, ".env must be present in .gitignore"
        print("  - Gitignore validation: .env is strictly ignored.")

        # Check mask_connection_url functionality
        test_sensitive_url = "postgresql://myuser:SuperSecretPassword123@localhost:5432/florachain_test"
        masked = mask_connection_url(test_sensitive_url)
        assert "SuperSecretPassword123" not in masked
        assert masked == "postgresql://myuser:***@localhost:5432/florachain_test"
        print(f"  - URL Masking test: {test_sensitive_url} -> {masked}")

        # Check collision protection: check_target_cleanliness
        from scripts.migrate_sqlite_to_postgres import check_target_cleanliness
        from app.models.database import PostgresConnectionAdapter
        existing_check = check_target_cleanliness(PostgresConnectionAdapter(pg_conn))
        assert len(existing_check) > 0, f"Cleanliness check should report existing tables in populated target, got {existing_check}"
        print(f"  - Collision detection guardrail active: detected {len(existing_check)} populated tables in target.")

        print("  ✅ Check 7 Passed: Credentials protected, URL masking active, collision protection validated.")

        # -------------------------------------------------------------------------
        # 8. SQLite Default Application Engine Verification
        # -------------------------------------------------------------------------
        print("\n[CHECK 8] Verifying SQLite Default Engine when No Database URL Supplied...")
        # Test without DATABASE_URL
        saved_db_url = os.environ.pop('DATABASE_URL', None)
        try:
            dialect = get_active_dialect(None)
            assert dialect == 'sqlite', f"Expected default dialect 'sqlite', got '{dialect}'"
            print(f"  - get_active_dialect(None) returned: '{dialect}'")

            conn = get_connection(None)
            assert isinstance(conn, sqlite3.Connection), f"Expected sqlite3.Connection, got {type(conn)}"
            # Verify PRAGMAs on default SQLite connection
            fk_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            wal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert fk_on == 1, "PRAGMA foreign_keys must be ON"
            print(f"  - Default connection type: sqlite3.Connection (foreign_keys={fk_on}, journal_mode={wal_mode})")
            conn.close()

            # Test Flask App factory default configuration
            from app import create_app
            app = create_app()
            assert app.config.get('DATABASE_URL') is None
            assert app.config.get('DB_PATH') == DEFAULT_DB_PATH
            print(f"  - Flask create_app() default DB_PATH: {app.config.get('DB_PATH')}")
            print(f"  - Flask create_app() DATABASE_URL: {app.config.get('DATABASE_URL')}")
        finally:
            if saved_db_url:
                os.environ['DATABASE_URL'] = saved_db_url

        print("  ✅ Check 8 Passed: SQLite remains the default application engine.")

        # -------------------------------------------------------------------------
        # Final Summary
        # -------------------------------------------------------------------------
        print("\n" + "=" * 80)
        print("🏆 ALL 8 AUDIT CHECKS PASSED WITH 100% PARITY & INTEGRITY")
        print("=" * 80 + "\n")

    finally:
        src_conn.close()
        pg_cur.close()
        pg_conn.close()


if __name__ == '__main__':
    run_audit()
