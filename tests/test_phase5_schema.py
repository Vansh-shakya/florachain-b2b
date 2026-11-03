"""
FloraChain B2B — Phase 5 Schema Test Suite
Tests the plants table creation, constraints, indexes, and seed data
against a TEMPORARY in-memory database (production data untouched).
"""

import sys
import os
import tempfile

# Force UTF-8 stdout if needed on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.database import init_database, get_connection

PASS = 0
FAIL = 0

def report(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} - {detail}")


def run_tests():
    global PASS, FAIL

    # Use a temporary file database (not in-memory, so WAL mode works)
    tmp_dir = tempfile.mkdtemp(prefix="florachain_test_")
    tmp_db = os.path.join(tmp_dir, "test_phase5.db")

    print("=" * 68)
    print("FLORACHAIN B2B — PHASE 5 SCHEMA TEST SUITE")
    print(f"Temporary DB: {tmp_db}")
    print("=" * 68)

    # ── TEST 1: Schema applies cleanly ──────────────────────────────────
    print("\n--- TEST 1: Schema Application & Table Creation ---")
    try:
        init_database(tmp_db)
        report("init_database() completed without errors", True)
    except Exception as e:
        report("init_database() completed without errors", False, str(e))
        return

    conn = get_connection(tmp_db)

    # ── TEST 2: plants table exists ─────────────────────────────────────
    print("\n--- TEST 2: Plants Table Existence ---")
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    report("plants table exists in database", "plants" in tables, f"Tables found: {tables}")

    # ── TEST 3: Column structure matches spec ───────────────────────────
    print("\n--- TEST 3: Plants Table Column Structure ---")
    columns = conn.execute("PRAGMA table_info(plants)").fetchall()
    col_names = [c[1] for c in columns]
    expected_cols = [
        "id", "common_name", "botanical_name", "category", "container_size",
        "unit", "unit_price", "stock_qty", "min_order_qty", "description",
        "status", "supplier_user_id", "created_at", "updated_at"
    ]
    for col in expected_cols:
        report(f"Column '{col}' exists", col in col_names, f"Found: {col_names}")

    report(f"Total column count is {len(expected_cols)}", len(col_names) == len(expected_cols),
           f"Expected {len(expected_cols)}, got {len(col_names)}")

    # ── TEST 4: Indexes created ─────────────────────────────────────────
    print("\n--- TEST 4: Plant Indexes ---")
    indexes = [r[1] for r in conn.execute(
        "SELECT * FROM sqlite_master WHERE type='index' AND tbl_name='plants'"
    ).fetchall()]
    for idx_name in ["idx_plants_supplier", "idx_plants_category", "idx_plants_status"]:
        report(f"Index '{idx_name}' exists", idx_name in indexes, f"Found: {indexes}")

    # ── TEST 5: Seed data populated ─────────────────────────────────────
    print("\n--- TEST 5: Seed Data Population ---")
    plant_count = conn.execute("SELECT COUNT(*) FROM plants").fetchone()[0]
    report(f"Plants seeded (count: {plant_count})", plant_count == 6, f"Expected 6, got {plant_count}")

    plants = conn.execute("SELECT common_name, category, unit_price, stock_qty, status FROM plants ORDER BY id").fetchall()
    for p in plants:
        print(f"    * {p[0]:30s} | {p[1]:12s} | Rs.{p[2]:>8.2f} | Stock: {p[3]:>4d} | {p[4]}")

    # ── TEST 6: CHECK constraints enforce valid data ────────────────────
    print("\n--- TEST 6: CHECK Constraint Enforcement ---")
    supplier_id = conn.execute("SELECT id FROM users WHERE role = 'SUPPLIER' LIMIT 1").fetchone()[0]

    # 6a: Invalid category rejected
    try:
        conn.execute(
            "INSERT INTO plants (common_name, category, container_size, unit_price, supplier_user_id) VALUES (?, ?, ?, ?, ?)",
            ("Test Plant", "INVALID_CATEGORY", "6-inch Pot", 100.0, supplier_id)
        )
        report("Invalid category CHECK constraint", False, "INSERT should have been rejected")
    except Exception:
        report("Invalid category CHECK constraint blocks bad data", True)

    # 6b: Negative price rejected
    try:
        conn.execute(
            "INSERT INTO plants (common_name, category, container_size, unit_price, supplier_user_id) VALUES (?, ?, ?, ?, ?)",
            ("Test Plant", "INDOOR", "6-inch Pot", -50.0, supplier_id)
        )
        report("Negative price CHECK constraint", False, "INSERT should have been rejected")
    except Exception:
        report("Negative price CHECK constraint blocks bad data", True)

    # 6c: Negative stock rejected
    try:
        conn.execute(
            "INSERT INTO plants (common_name, category, container_size, unit_price, stock_qty, supplier_user_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("Test Plant", "INDOOR", "6-inch Pot", 100.0, -10, supplier_id)
        )
        report("Negative stock CHECK constraint", False, "INSERT should have been rejected")
    except Exception:
        report("Negative stock CHECK constraint blocks bad data", True)

    # 6d: Invalid unit rejected
    try:
        conn.execute(
            "INSERT INTO plants (common_name, category, container_size, unit, unit_price, supplier_user_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("Test Plant", "INDOOR", "6-inch Pot", "kilogram", 100.0, supplier_id)
        )
        report("Invalid unit CHECK constraint", False, "INSERT should have been rejected")
    except Exception:
        report("Invalid unit CHECK constraint blocks bad data", True)

    # 6e: Invalid status rejected
    try:
        conn.execute(
            "INSERT INTO plants (common_name, category, container_size, unit_price, status, supplier_user_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("Test Plant", "INDOOR", "6-inch Pot", 100.0, "DELETED", supplier_id)
        )
        report("Invalid status CHECK constraint", False, "INSERT should have been rejected")
    except Exception:
        report("Invalid status CHECK constraint blocks bad data", True)

    # ── TEST 7: Foreign key references users table ──────────────────────
    print("\n--- TEST 7: Foreign Key Integrity ---")
    try:
        conn.execute(
            "INSERT INTO plants (common_name, category, container_size, unit_price, supplier_user_id) VALUES (?, ?, ?, ?, ?)",
            ("Phantom Plant", "INDOOR", "6-inch Pot", 100.0, 99999)
        )
        report("FK constraint on supplier_user_id", False, "INSERT with non-existent user should fail")
    except Exception:
        report("FK constraint blocks non-existent supplier_user_id", True)

    # ── TEST 8: Existing tables unharmed ────────────────────────────────
    print("\n--- TEST 8: Existing Tables Unharmed ---")
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    report(f"Users table has seed data ({user_count} records)", user_count == 3)
    order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    report(f"Orders table has seed data ({order_count} records)", order_count == 3)
    agr_count = conn.execute("SELECT COUNT(*) FROM deal_agreements").fetchone()[0]
    report(f"Deal agreements table has seed data ({agr_count} records)", agr_count == 2)
    insp_count = conn.execute("SELECT COUNT(*) FROM delivery_inspections").fetchone()[0]
    report(f"Delivery inspections table has seed data ({insp_count} records)", insp_count == 1)

    # ── TEST 9: Idempotent re-initialization ────────────────────────────
    print("\n--- TEST 9: Idempotent Re-initialization ---")
    conn.close()
    try:
        init_database(tmp_db)
        conn2 = get_connection(tmp_db)
        plant_count_2 = conn2.execute("SELECT COUNT(*) FROM plants").fetchone()[0]
        report(f"Second init_database() is safe (plants: {plant_count_2})", plant_count_2 == 6,
               f"Expected 6 (no duplicates), got {plant_count_2}")
        user_count_2 = conn2.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        report(f"Users not duplicated after re-init ({user_count_2})", user_count_2 == 3)
        conn2.close()
    except Exception as e:
        report("Re-initialization is idempotent", False, str(e))

    # ── SUMMARY ─────────────────────────────────────────────────────────
    print("\n" + "=" * 68)
    total = PASS + FAIL
    print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")
    if FAIL == 0:
        print("ALL PHASE 5 SCHEMA TESTS PASSED SUCCESSFULLY!")
    else:
        print(f"{FAIL} test(s) failed - review above.")
    print("=" * 68)

    # Clean up temp file
    try:
        os.remove(tmp_db)
        # Remove WAL/SHM files if they exist
        for suffix in ['-wal', '-shm']:
            wal_path = tmp_db + suffix
            if os.path.exists(wal_path):
                os.remove(wal_path)
        os.rmdir(tmp_dir)
    except Exception:
        pass

    return FAIL == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

