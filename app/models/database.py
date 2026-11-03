"""
FloraChain B2B — Dual-Engine Database Adapter & Connection Engine
Phase 14: Relational SQLite & PostgreSQL Adapter with Unified Service Interface
"""

import sqlite3
import os
import re
import json
from collections.abc import Mapping
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DEFAULT_DB_PATH = os.path.join(DATA_DIR, 'florachain.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')
SCHEMA_POSTGRES_PATH = os.path.join(os.path.dirname(__file__), 'schema_postgres.sql')

TABLES_WITH_AUTO_ID = {
    'users',
    'delivery_inspections',
    'inspection_confirmations',
    'audit_events',
    'inspection_corrections',
    'plants',
    'deal_agreements',
    'agreement_approvals',
    'order_items',
    'invoice_items',
    'payment_allocations',
}

def ensure_data_directory(db_path=DEFAULT_DB_PATH):
    folder = os.path.dirname(db_path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

def is_postgres_url(target):
    """
    Returns True if the target connection string starts with postgresql:// or postgres://.
    """
    if not target or not isinstance(target, str):
        return False
    clean = target.strip().lower()
    return clean.startswith('postgresql://') or clean.startswith('postgres://')

def get_active_dialect(db_target=None):
    """
    Determines whether the active database engine is 'postgresql' or 'sqlite'.
    """
    if db_target and is_postgres_url(db_target):
        return 'postgresql'
    if db_target is None:
        try:
            from flask import current_app, has_app_context
            if has_app_context() and current_app:
                cfg_url = current_app.config.get('DATABASE_URL')
                if cfg_url and is_postgres_url(cfg_url):
                    return 'postgresql'
        except (ImportError, RuntimeError):
            pass
        env_url = os.environ.get('DATABASE_URL')
        if env_url and is_postgres_url(env_url):
            return 'postgresql'
    return 'sqlite'

def translate_sql_placeholders(sql):
    """
    Translates SQLite positional '?' parameter placeholders to PostgreSQL '%s'
    while strictly preserving '?' characters inside single- or double-quoted string literals.
    """
    result = []
    in_single_quote = False
    in_double_quote = False
    i = 0
    n = len(sql)
    while i < n:
        char = sql[i]
        if char == "'" and not in_double_quote:
            if in_single_quote and i + 1 < n and sql[i + 1] == "'":
                result.append("''")
                i += 2
                continue
            in_single_quote = not in_single_quote
            result.append(char)
        elif char == '"' and not in_single_quote:
            if in_double_quote and i + 1 < n and sql[i + 1] == '"':
                result.append('""')
                i += 2
                continue
            in_double_quote = not in_double_quote
            result.append(char)
        elif char == '?' and not in_single_quote and not in_double_quote:
            result.append('%s')
        else:
            result.append(char)
        i += 1
    return "".join(result)

def extract_insert_target_table(sql):
    """
    Extracts the destination table name from an INSERT statement.
    """
    m = re.search(r'INSERT\s+INTO\s+([a-zA-Z0-9_\.]+)', sql, re.IGNORECASE)
    if m:
        table_raw = m.group(1).split('.')[-1].strip().lower()
        return table_raw
    return None

class PostgresRow(Mapping):
    """
    Adapter row representation providing parity with sqlite3.Row:
    - Key-based access: row['column_name'] (case-preserving and case-insensitive fallback)
    - Index-based access: row[0]
    - dict(row) mapping compatibility
    - Safe .get(key, default)
    - 'column' in row containment check
    """
    def __init__(self, columns, values):
        self._columns = tuple(columns)
        self._values = tuple(values)
        self._map = {col: val for col, val in zip(columns, values)}
        self._lower_map = {col.lower(): val for col, val in zip(columns, values)}

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        if key in self._map:
            return self._map[key]
        if isinstance(key, str) and key.lower() in self._lower_map:
            return self._lower_map[key.lower()]
        raise KeyError(key)

    def __iter__(self):
        return iter(self._columns)

    def __len__(self):
        return len(self._columns)

    def keys(self):
        return self._columns

    def values(self):
        return self._values

    def items(self):
        return zip(self._columns, self._values)

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def __contains__(self, key):
        if isinstance(key, str):
            return key in self._map or key.lower() in self._lower_map
        return False

    def __repr__(self):
        return f"<PostgresRow {dict(self)}>"

class PostgresCursorAdapter:
    """
    Cursor adapter wrapping a PEP 249 psycopg2 cursor:
    - Translates SQL placeholders ('?' -> '%s')
    - Appends 'RETURNING id' for INSERT statements on autoincrement tables
    - Exposes cursor.lastrowid
    - Wraps result rows in PostgresRow
    """
    def __init__(self, raw_cursor):
        self._cur = raw_cursor
        self.lastrowid = None

    def execute(self, sql, params=None):
        params = () if params is None else params
        target_table = extract_insert_target_table(sql)
        is_insert = bool(target_table)
        has_returning = bool(re.search(r'\bRETURNING\b', sql, re.IGNORECASE))
        appended_returning = False

        if is_insert and not has_returning and target_table in TABLES_WITH_AUTO_ID:
            clean_sql = sql.rstrip().rstrip(';')
            sql = f"{clean_sql} RETURNING id;"
            appended_returning = True

        translated_sql = translate_sql_placeholders(sql)
        self._cur.execute(translated_sql, params)

        if appended_returning:
            row = self._cur.fetchone()
            self.lastrowid = row[0] if row else None
        else:
            self.lastrowid = None

        return self

    def executemany(self, sql, params_list):
        translated_sql = translate_sql_placeholders(sql)
        self._cur.executemany(translated_sql, params_list)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in self._cur.description]
        return PostgresRow(cols, row)

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        cols = [desc[0] for desc in self._cur.description]
        return [PostgresRow(cols, r) for r in rows]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size is not None else self._cur.fetchmany()
        if not rows:
            return []
        cols = [desc[0] for desc in self._cur.description]
        return [PostgresRow(cols, r) for r in rows]

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def close(self):
        self._cur.close()

    def __iter__(self):
        return iter(self.fetchall())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class PostgresConnectionAdapter:
    """
    Connection adapter wrapping a raw psycopg2 connection to provide
    the exact same interface as sqlite3.Connection used across FloraChain services.
    """
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql, params=None):
        cur = self.cursor()
        return cur.execute(sql, params)

    def executemany(self, sql, params_list):
        cur = self.cursor()
        return cur.executemany(sql, params_list)

    def executescript(self, sql_script):
        cur = self.cursor()
        return cur.execute(sql_script)

    def cursor(self):
        return PostgresCursorAdapter(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

def parse_pg_url(url):
    """
    Parses a postgresql:// URL into connection parameters, correctly handling
    unencoded special characters (such as '@') in the password component.
    """
    import urllib.parse
    if not url or not isinstance(url, str):
        return None
    m = re.match(r'^(postgres(?:ql)?):\/\/(.*?)@([^\/@]+(?::\d+)?)\/([^?]+)(?:\?.*)?$', url)
    if not m:
        return None
    scheme, userinfo, hostport, dbname = m.groups()
    user, _, password = userinfo.partition(':')
    host, _, port = hostport.partition(':')
    return {
        'host': host,
        'port': int(port) if port else 5432,
        'dbname': dbname,
        'user': user,
        'password': urllib.parse.unquote(password)
    }


def get_postgres_connection(db_url):
    """
    Connects to PostgreSQL using psycopg2 and returns an adapted connection.
    """
    try:
        import psycopg2
    except ImportError as e:
        raise RuntimeError(
            "PostgreSQL driver 'psycopg2' is not installed in the Python environment. "
            "Please ensure psycopg2-binary is installed to connect to PostgreSQL."
        ) from e

    params = parse_pg_url(db_url)
    if params:
        conn = psycopg2.connect(**params)
    else:
        conn = psycopg2.connect(db_url)
    return PostgresConnectionAdapter(conn)

def get_connection(db_target=None):
    """
    Returns an optimized database connection based on active configuration:
    - If db_target or configured DATABASE_URL is PostgreSQL, returns an adapted PostgreSQL connection.
    - Otherwise, returns an optimized SQLite connection with:
      * Foreign keys enabled (PRAGMA foreign_keys = ON)
      * Write-Ahead Logging (WAL) enabled
      * 5000ms busy timeout
      * sqlite3.Row row factory
    """
    dialect = get_active_dialect(db_target)
    if dialect == 'postgresql':
        db_url = db_target
        if not db_url:
            try:
                from flask import current_app, has_app_context
                if has_app_context() and current_app:
                    db_url = current_app.config.get('DATABASE_URL')
            except (ImportError, RuntimeError):
                pass
        if not db_url:
            db_url = os.environ.get('DATABASE_URL')
        return get_postgres_connection(db_url)

    # SQLite connection path
    db_path = db_target
    if db_path is None:
        try:
            from flask import current_app, has_app_context
            if has_app_context() and current_app and 'DB_PATH' in current_app.config:
                db_path = current_app.config['DB_PATH']
        except (ImportError, RuntimeError):
            pass
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    ensure_data_directory(db_path)
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

def get_db(db_path=None):
    """
    Returns a request-scoped database connection cached on Flask's `g`.
    Automatically closed at the end of the request via teardown_appcontext.
    """
    try:
        from flask import g, has_app_context
        if has_app_context():
            if 'db' not in g:
                g.db = get_connection(db_path)
            return g.db
    except (ImportError, RuntimeError):
        pass
    return get_connection(db_path)

def close_db(e=None):
    """
    Closes the request-scoped database connection stored on Flask's `g`, if any.
    Registered as a teardown_appcontext handler in the application factory.
    """
    try:
        from flask import g, has_app_context
        if has_app_context():
            db = g.pop('db', None)
            if db is not None:
                db.close()
    except (ImportError, RuntimeError):
        pass

def init_database(db_path=None):
    """
    Applies the appropriate relational schema and populates initial B2B seed data if not present.
    - If PostgreSQL: applies schema_postgres.sql.
    - If SQLite: applies schema.sql and runs incremental migration routines if needed.
    """
    dialect = get_active_dialect(db_path)
    if dialect == 'postgresql':
        conn = get_connection(db_path)
        try:
            with open(SCHEMA_POSTGRES_PATH, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            with conn:
                conn.execute(schema_sql)
        finally:
            conn.close()
        return

    # SQLite initialization
    target_path = db_path if db_path else DEFAULT_DB_PATH
    ensure_data_directory(target_path)
    conn = get_connection(target_path)
    with conn:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        
        # Check if users already seeded
        cursor = conn.execute("SELECT COUNT(*) FROM users;")
        user_count = cursor.fetchone()[0]
        if user_count == 0:
            seed_initial_data(conn)
        else:
            ensure_orders_schema_updated(conn)
            ensure_truck_loading_schema_updated(conn)
            ensure_deal_agreements_seeded(conn)
            ensure_plants_seeded(conn)
            ensure_order_items_seeded(conn)
            ensure_item_inspections_schema_updated(conn)
            ensure_invoices_schema_updated(conn)
            ensure_invoices_seeded(conn)
            ensure_payments_schema_updated(conn)
            ensure_payments_seeded(conn)
    conn.close()

def seed_deal_agreements(conn):
    """
    Seeds initial demonstration digital deal agreements.
    """
    supplier_row = conn.execute("SELECT id FROM users WHERE username = 'supplier_rajesh'").fetchone()
    nursery_row = conn.execute("SELECT id FROM users WHERE username = 'nursery_amit'").fetchone()
    if not supplier_row or not nursery_row:
        return

    supplier_id = supplier_row[0]
    nursery_id = nursery_row[0]

    # 1. Agreed deal for ORD-8760
    ord_8760 = conn.execute("SELECT * FROM orders WHERE id = 'ORD-8760'").fetchone()
    if ord_8760:
        total_val = round(ord_8760['ordered_qty'] * ord_8760['unit_price'], 2) # 42000.0
        adv_pct = 25.0
        adv_amt = 10500.0
        bal_amt = 31500.0
        conn.execute(
            """INSERT INTO deal_agreements 
               (agreement_ref, order_id, version, supplier_user_id, nursery_user_id, plant_variety,
                quantity, unit_price, total_order_value, advance_percentage, advance_amount, balance_amount,
                payment_due_date, payment_period_days, interest_rate_pct, interest_calculation_basis,
                interest_grace_period_days, notes, status, created_by_user_id, agreed_at)
               VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 10, 18.0, 'ANNUAL_SIMPLE', 0, ?, 'AGREED', ?, CURRENT_TIMESTAMP)""",
            ("AGR-8760-v1", "ORD-8760", supplier_id, nursery_id, ord_8760['variety'],
             ord_8760['ordered_qty'], ord_8760['unit_price'], total_val, adv_pct, adv_amt, bal_amt,
             "2026-10-25", "Agreed 25% upfront advance; balance payable within 10 days of delivery.", supplier_id)
        )
        agr_8760_id = conn.execute("SELECT id FROM deal_agreements WHERE agreement_ref = 'AGR-8760-v1'").fetchone()[0]

        snapshot_8760 = json.dumps({
            "agreement_ref": "AGR-8760-v1",
            "order_id": "ORD-8760",
            "total_order_value": total_val,
            "advance_amount": adv_amt,
            "balance_amount": bal_amt,
            "payment_due_date": "2026-10-25",
            "interest_rate_pct": 18.0
        })

        conn.execute(
            """INSERT INTO agreement_approvals (agreement_id, party_role, user_id, approval_type, terms_snapshot_json, notes)
               VALUES (?, 'SUPPLIER', ?, 'IN_APP_CLICK', ?, 'Terms approved by wholesale supplier dispatch head.')""",
            (agr_8760_id, supplier_id, snapshot_8760)
        )
        conn.execute(
            """INSERT INTO agreement_approvals (agreement_id, party_role, user_id, approval_type, terms_snapshot_json, notes)
               VALUES (?, 'NURSERY', ?, 'IN_APP_CLICK', ?, 'Terms approved by nursery procurement manager.')""",
            (agr_8760_id, nursery_id, snapshot_8760)
        )

        conn.execute(
            """INSERT INTO audit_events (event_type, order_id, actor_user_id, actor_role, after_state_json, justification)
               VALUES ('AGREEMENT_AGREED', 'ORD-8760', ?, 'SYSTEM', ?, 'Dual party agreement finalized; both supplier and nursery assented to terms.')""",
            (supplier_id, snapshot_8760)
        )

    # 2. Pending counterparty approval deal for ORD-8801 (Supplier approved, awaiting Nursery)
    ord_8801 = conn.execute("SELECT * FROM orders WHERE id = 'ORD-8801'").fetchone()
    if ord_8801:
        total_val = round(ord_8801['ordered_qty'] * ord_8801['unit_price'], 2) # 52500.0
        adv_pct = 20.0
        adv_amt = 10500.0
        bal_amt = 42000.0
        conn.execute(
            """INSERT INTO deal_agreements 
               (agreement_ref, order_id, version, supplier_user_id, nursery_user_id, plant_variety,
                quantity, unit_price, total_order_value, advance_percentage, advance_amount, balance_amount,
                payment_due_date, payment_period_days, interest_rate_pct, interest_calculation_basis,
                interest_grace_period_days, notes, status, created_by_user_id)
               VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 10, 18.0, 'ANNUAL_SIMPLE', 0, ?, 'PENDING_COUNTERPARTY_APPROVAL', ?)""",
            ("AGR-8801-v1", "ORD-8801", supplier_id, nursery_id, ord_8801['variety'],
             ord_8801['ordered_qty'], ord_8801['unit_price'], total_val, adv_pct, adv_amt, bal_amt,
             "2026-10-28", "Standard commercial deal: 20% advance, balance 80% due within 10 days of physical delivery.", supplier_id)
        )
        agr_8801_id = conn.execute("SELECT id FROM deal_agreements WHERE agreement_ref = 'AGR-8801-v1'").fetchone()[0]

        snapshot_8801 = json.dumps({
            "agreement_ref": "AGR-8801-v1",
            "order_id": "ORD-8801",
            "total_order_value": total_val,
            "advance_amount": adv_amt,
            "balance_amount": bal_amt,
            "payment_due_date": "2026-10-28",
            "interest_rate_pct": 18.0
        })

        conn.execute(
            """INSERT INTO agreement_approvals (agreement_id, party_role, user_id, approval_type, terms_snapshot_json, notes)
               VALUES (?, 'SUPPLIER', ?, 'IN_APP_CLICK', ?, 'Supplier proposed terms and registered initial in-app consent.')""",
            (agr_8801_id, supplier_id, snapshot_8801)
        )

        conn.execute(
            """INSERT INTO audit_events (event_type, order_id, actor_user_id, actor_role, after_state_json, justification)
               VALUES ('AGREEMENT_CREATED', 'ORD-8801', ?, 'SUPPLIER', ?, 'Digital deal agreement AGR-8801-v1 created by supplier; awaiting nursery consent.')""",
            (supplier_id, snapshot_8801)
        )

def ensure_deal_agreements_seeded(conn):
    """
    Checks if deal_agreements table has records; if empty, populates demo agreements.
    """
    try:
        count = conn.execute("SELECT COUNT(*) FROM deal_agreements").fetchone()[0]
        if count == 0:
            seed_deal_agreements(conn)
    except sqlite3.OperationalError:
        pass

def seed_plants_catalog(conn):
    """
    Seeds initial demonstration wholesale plant catalog entries.
    Plant data aligns with existing order varieties and frontend catalog preview.
    """
    supplier_row = conn.execute("SELECT id FROM users WHERE username = 'supplier_rajesh'").fetchone()
    if not supplier_row:
        return

    supplier_id = supplier_row[0]

    plants_data = [
        # (common_name, botanical_name, category, container_size, unit, unit_price, stock_qty, min_order_qty, description, status)
        ("Areca Palm", "Dypsis lutescens", "PALM", "12-inch Nursery Pot", "pot", 350.0, 450, 10,
         "Popular indoor palm. Dense feathery fronds, excellent air purifier. Supplied as 3-foot nursery-ready stock.", "ACTIVE"),
        ("Bougainvillea Dwarf", "Bougainvillea glabra", "FLOWERING", "8-inch Heavy Bag", "bag", 180.0, 800, 25,
         "Compact flowering shrub with vibrant magenta bracts. Hardy, drought-tolerant. Suitable for borders and containers.", "ACTIVE"),
        ("Ficus Lyrata Bambino", "Ficus lyrata 'Bambino'", "INDOOR", "10-inch Nursery Pot", "pot", 650.0, 200, 5,
         "Compact fiddle leaf fig variety. Lush, dark green violin-shaped leaves. Premium indoor specimen plant.", "ACTIVE"),
        ("Monstera Deliciosa", "Monstera deliciosa", "INDOOR", "12-inch Nursery Pot", "pot", 550.0, 150, 5,
         "Iconic split-leaf philodendron. Mature fenestrated foliage. High-value indoor statement plant.", "ACTIVE"),
        ("Golden Pothos Totem", "Epipremnum aureum", "CLIMBER", "3-foot Totem Pole", "plant", 420.0, 320, 10,
         "Vigorous climbing aroid trained on moss totem. Variegated golden-green foliage. Low-maintenance indoor vertical accent.", "ACTIVE"),
        ("Adenium Desert Rose", "Adenium obesum", "SUCCULENT", "6-inch Ceramic Pot", "pot", 280.0, 100, 10,
         "Sculptural caudex succulent with vibrant pink-red trumpet flowers. Drought-tolerant. Collector-grade grafted specimens.", "ACTIVE"),
    ]

    conn.executemany(
        """INSERT INTO plants
           (common_name, botanical_name, category, container_size, unit, unit_price, stock_qty, min_order_qty, description, status, supplier_user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], supplier_id) for p in plants_data]
    )

def ensure_plants_seeded(conn):
    """
    Checks if plants table has records; if empty, populates demo catalog.
    """
    try:
        count = conn.execute("SELECT COUNT(*) FROM plants").fetchone()[0]
        if count == 0:
            seed_plants_catalog(conn)
    except sqlite3.OperationalError:
        pass

def seed_initial_data(conn):
    """
    Seeds initial demonstration accounts and wholesale orders.
    """
    default_pw_hash = generate_password_hash("password123")

    users_data = [
        ("supplier_rajesh", "supplier@greenrootsfarms.com", default_pw_hash, "SUPPLIER", "GreenRoots Wholesale Farms"),
        ("nursery_amit", "purchasing@greenmeadows.com", default_pw_hash, "NURSERY", "Green Meadows Landscape Nursery"),
        ("admin_flora", "compliance@florachain.io", default_pw_hash, "ADMIN", "FloraChain B2B Compliance & Audit Authority")
    ]

    conn.executemany(
        """INSERT INTO users (username, email, password_hash, role, business_name)
           VALUES (?, ?, ?, ?, ?)""",
        users_data
    )

    # Fetch user IDs
    supplier_id = conn.execute("SELECT id FROM users WHERE username = 'supplier_rajesh'").fetchone()[0]
    nursery_id = conn.execute("SELECT id FROM users WHERE username = 'nursery_amit'").fetchone()[0]
    admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin_flora'").fetchone()[0]

    orders_data = [
        ("ORD-8801", supplier_id, nursery_id, "Areca Palm (12-inch Pot)", 150, 350.0, "KA-04-E-8821", "Ramesh Kumar (+91 98450 12345)", "DISPATCHED"),
        ("ORD-8802", supplier_id, nursery_id, "Bougainvillea Dwarf (8-inch Bag)", 300, 180.0, "KA-05-MH-4412", "Suresh Patil (+91 97401 55678)", "DISPATCHED"),
        ("ORD-8760", supplier_id, nursery_id, "Golden Pothos Totem (3-foot)", 100, 420.0, "DL-01-AX-9901", "Harpreet Singh (+91 98110 33221)", "LOCKED_VERIFIED")
    ]

    conn.executemany(
        """INSERT INTO orders (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, truck_no, driver_info, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        orders_data
    )

    # Seed pre-verified locked delivery for ORD-8760 (demonstrating finalized dual confirmation)
    conn.execute(
        """INSERT INTO delivery_inspections 
           (order_id, delivered_qty, sound_qty, damaged_qty, damage_pct, damage_notes, has_mismatch, mismatch_diff, status, is_locked, locked_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
        ("ORD-8760", 100, 98, 2, 2.0, "2 totems bent during truck loading; root stock intact.", 0, 0, "LOCKED_VERIFIED")
    )
    insp_id = conn.execute("SELECT id FROM delivery_inspections WHERE order_id = 'ORD-8760'").fetchone()[0]

    # Both parties counter-signed ORD-8760
    conn.execute(
        """INSERT INTO inspection_confirmations (inspection_id, party_role, user_id, signature_note)
           VALUES (?, 'NURSERY', ?, 'Physical inspection verified at nursery intake dock.')""",
        (insp_id, nursery_id)
    )
    conn.execute(
        """INSERT INTO inspection_confirmations (inspection_id, party_role, user_id, signature_note)
           VALUES (?, 'SUPPLIER', ?, 'Counter-signed by dispatch manager; 2 damaged units credited.')""",
        (insp_id, supplier_id)
    )

    # Audit event for ORD-8760 lock
    conn.execute(
        """INSERT INTO audit_events (event_type, order_id, actor_user_id, actor_role, after_state_json, justification)
           VALUES (?, ?, ?, 'SYSTEM', ?, 'Dual confirmation finalized; order permanently locked.')""",
        ("ORDER_LOCKED", "ORD-8760", admin_id, json.dumps({
            "order_id": "ORD-8760",
            "sound_qty": 98,
            "damaged_qty": 2,
            "damage_pct": 2.0,
            "is_locked": 1
        }))
    )

    # Seed deal agreements
    seed_deal_agreements(conn)

    # Seed wholesale plant catalog
    seed_plants_catalog(conn)

    # Seed wholesale order line items
    seed_order_items(conn)

    # Seed item inspections & wholesale invoices
    ensure_item_inspections_schema_updated(conn)
    ensure_invoices_schema_updated(conn)
    seed_invoices(conn)

    # Seed wholesale payments (Phase 9)
    ensure_payments_schema_updated(conn)
    seed_payments(conn)

def ensure_orders_schema_updated(conn):
    """
    Ensures orders table schema supports Phase 6 statuses (e.g. 'CONFIRMED', 'DRAFT')
    and default values for truck_no and driver_info.
    Safely migrates existing data without data loss or foreign key violations.
    """
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
    if row and 'CONFIRMED' not in row[0]:
        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute("""
            CREATE TABLE orders_new (
                id TEXT PRIMARY KEY,
                supplier_user_id INTEGER NOT NULL REFERENCES users(id),
                nursery_user_id INTEGER NOT NULL REFERENCES users(id),
                variety TEXT NOT NULL,
                ordered_qty INTEGER NOT NULL CHECK(ordered_qty > 0),
                unit_price REAL NOT NULL CHECK(unit_price > 0),
                truck_no TEXT NOT NULL DEFAULT 'TBD',
                driver_info TEXT NOT NULL DEFAULT 'TBD',
                status TEXT NOT NULL CHECK(status IN (
                    'DRAFT', 'CONFIRMED', 'STAGING', 'DISPATCHED',
                    'INSPECTED_PENDING_CONFIRMATION', 'DELIVERED', 'LOCKED_VERIFIED', 'CANCELLED'
                )),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            INSERT INTO orders_new (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, truck_no, driver_info, status, created_at)
            SELECT id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, truck_no, driver_info, status, created_at FROM orders;
        """)
        conn.execute("DROP TABLE orders;")
        conn.execute("ALTER TABLE orders_new RENAME TO orders;")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_supplier ON orders(supplier_user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_nursery ON orders(nursery_user_id);")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON;")

def seed_order_items(conn):
    """
    Seeds initial order line items for seeded demo wholesale batches.
    Maps existing orders to plant catalog items:
    - ORD-8801: Areca Palm (id 1)
    - ORD-8802: Bougainvillea Dwarf (id 2)
    - ORD-8760: Golden Pothos Totem (id 5)
    """
    plant_rows = conn.execute("SELECT id, common_name, unit_price FROM plants").fetchall()
    plant_by_name = {p['common_name']: p for p in plant_rows}

    orders = conn.execute("SELECT id, variety, ordered_qty, unit_price FROM orders").fetchall()
    for o in orders:
        order_id = o['id']
        qty = o['ordered_qty']
        price = o['unit_price']
        line_total = round(qty * price, 2)
        plant_id = None
        if 'Areca' in o['variety'] and 'Areca Palm' in plant_by_name:
            plant_id = plant_by_name['Areca Palm']['id']
        elif 'Bougainvillea' in o['variety'] and 'Bougainvillea Dwarf' in plant_by_name:
            plant_id = plant_by_name['Bougainvillea Dwarf']['id']
        elif 'Pothos' in o['variety'] and 'Golden Pothos Totem' in plant_by_name:
            plant_id = plant_by_name['Golden Pothos Totem']['id']

        # Check if already has items
        item_exists = conn.execute("SELECT COUNT(*) FROM order_items WHERE order_id = ?", (order_id,)).fetchone()[0]
        if item_exists == 0:
            conn.execute(
                """INSERT INTO order_items (order_id, plant_id, variety, quantity, unit_price, line_total, loaded_qty)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (order_id, plant_id, o['variety'], qty, price, line_total, qty)
            )

def ensure_truck_loading_schema_updated(conn):
    """
    Ensures order_items table has loaded_qty column and orders table has loaded_at / loading_notes.
    Safely migrates existing databases without data loss.
    """
    try:
        # 1. Check order_items columns
        item_cols = [c[1] for c in conn.execute("PRAGMA table_info(order_items)").fetchall()]
        if 'loaded_qty' not in item_cols:
            conn.execute("ALTER TABLE order_items ADD COLUMN loaded_qty INTEGER NOT NULL DEFAULT 0 CHECK(loaded_qty >= 0 AND loaded_qty <= quantity);")
            conn.execute("UPDATE order_items SET loaded_qty = quantity WHERE order_id IN ('ORD-8801', 'ORD-8802', 'ORD-8760');")

        # 2. Check orders columns
        order_cols = [c[1] for c in conn.execute("PRAGMA table_info(orders)").fetchall()]
        if 'loaded_at' not in order_cols:
            conn.execute("ALTER TABLE orders ADD COLUMN loaded_at DATETIME NULL;")
            conn.execute("UPDATE orders SET loaded_at = created_at WHERE id IN ('ORD-8801', 'ORD-8802', 'ORD-8760');")
        if 'loading_notes' not in order_cols:
            conn.execute("ALTER TABLE orders ADD COLUMN loading_notes TEXT DEFAULT '';")
    except sqlite3.OperationalError:
        pass

def ensure_order_items_seeded(conn):
    """
    Ensures order_items table has records for seeded orders.
    """
    try:
        count = conn.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
        if count == 0:
            seed_order_items(conn)
    except sqlite3.OperationalError:
        pass

def ensure_item_inspections_schema_updated(conn):
    """
    Ensures order_items table has item-level inspection columns (delivered_qty, sound_qty, damaged_qty).
    Safely migrates existing databases without data loss.
    """
    try:
        item_cols = [c[1] for c in conn.execute("PRAGMA table_info(order_items)").fetchall()]
        if 'delivered_qty' not in item_cols:
            conn.execute("ALTER TABLE order_items ADD COLUMN delivered_qty INTEGER NULL;")
        if 'sound_qty' not in item_cols:
            conn.execute("ALTER TABLE order_items ADD COLUMN sound_qty INTEGER NULL;")
        if 'damaged_qty' not in item_cols:
            conn.execute("ALTER TABLE order_items ADD COLUMN damaged_qty INTEGER DEFAULT 0;")

        # Populate historical delivered counts for locked demo batches
        conn.execute("UPDATE order_items SET delivered_qty = 100, sound_qty = 98, damaged_qty = 2 WHERE order_id = 'ORD-8760' AND sound_qty IS NULL;")
        conn.execute("UPDATE order_items SET delivered_qty = 150, sound_qty = 145, damaged_qty = 5 WHERE order_id = 'ORD-8801' AND sound_qty IS NULL;")
    except sqlite3.OperationalError:
        pass

def ensure_invoices_schema_updated(conn):
    """
    Ensures invoices and invoice_items tables and indexes exist.
    """
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id TEXT PRIMARY KEY,
                invoice_number TEXT UNIQUE NOT NULL,
                order_id TEXT NOT NULL REFERENCES orders(id),
                supplier_user_id INTEGER NOT NULL REFERENCES users(id),
                nursery_user_id INTEGER NOT NULL REFERENCES users(id),
                inspection_id INTEGER REFERENCES delivery_inspections(id),
                invoice_date TEXT NOT NULL,
                due_date TEXT NULL,
                currency TEXT NOT NULL DEFAULT 'INR',
                subtotal REAL NOT NULL CHECK(subtotal >= 0),
                tax_rate_pct REAL NOT NULL DEFAULT 0.0 CHECK(tax_rate_pct >= 0),
                tax_amount REAL NOT NULL DEFAULT 0.0 CHECK(tax_amount >= 0),
                discount_amount REAL NOT NULL DEFAULT 0.0 CHECK(discount_amount >= 0),
                total_amount REAL NOT NULL CHECK(total_amount >= 0),
                total_quantity INTEGER NOT NULL CHECK(total_quantity >= 0),
                status TEXT NOT NULL DEFAULT 'ISSUED' CHECK(status IN ('DRAFT', 'ISSUED', 'CANCELLED')),
                damage_billing_policy TEXT DEFAULT 'CREDITED_EXCLUDED',
                notes TEXT DEFAULT '',
                terms_snapshot_json TEXT NULL,
                created_by_user_id INTEGER NOT NULL REFERENCES users(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                order_item_id INTEGER REFERENCES order_items(id),
                plant_id INTEGER REFERENCES plants(id),
                variety TEXT NOT NULL,
                botanical_name TEXT DEFAULT '',
                category TEXT DEFAULT '',
                container_size TEXT DEFAULT '',
                unit TEXT NOT NULL DEFAULT 'plant',
                ordered_qty INTEGER NOT NULL CHECK(ordered_qty >= 0),
                delivered_qty INTEGER NOT NULL CHECK(delivered_qty >= 0),
                sound_qty INTEGER NOT NULL CHECK(sound_qty >= 0),
                damaged_qty INTEGER NOT NULL DEFAULT 0 CHECK(damaged_qty >= 0),
                billable_qty INTEGER NOT NULL CHECK(billable_qty >= 0),
                unit_price REAL NOT NULL CHECK(unit_price > 0),
                damaged_unit_price REAL NOT NULL DEFAULT 0.0 CHECK(damaged_unit_price >= 0),
                line_total REAL NOT NULL CHECK(line_total >= 0),
                notes TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_invoices_order ON invoices(order_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_invoices_nursery ON invoices(nursery_user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_invoice_items_plant ON invoice_items(plant_id);")

        # Phase 10: Late-Payment Interest & Due Date Schema Migration
        inv_cols = [c[1] for c in conn.execute("PRAGMA table_info(invoices)").fetchall()]
        if 'interest_rate_pct' not in inv_cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN interest_rate_pct REAL NOT NULL DEFAULT 0.0;")
        if 'interest_calculation_basis' not in inv_cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN interest_calculation_basis TEXT NOT NULL DEFAULT 'ANNUAL_SIMPLE';")
        if 'interest_grace_period_days' not in inv_cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN interest_grace_period_days INTEGER NOT NULL DEFAULT 0;")
        if 'agreement_ref' not in inv_cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN agreement_ref TEXT NULL;")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_invoices_due ON invoices(due_date);")

        # Ensure demo invoice INV-2026-8760 carries contractual agreement terms from AGR-8760-v1
        conn.execute(
            """UPDATE invoices 
               SET interest_rate_pct = 18.0, interest_calculation_basis = 'ANNUAL_SIMPLE', interest_grace_period_days = 0, agreement_ref = 'AGR-8760-v1', due_date = '2026-10-26'
               WHERE id = 'INV-2026-8760' AND (interest_rate_pct = 0.0 OR agreement_ref IS NULL)"""
        )
    except sqlite3.OperationalError:
        pass

def seed_invoices(conn):
    """
    Seeds initial demonstration wholesale invoice for pre-verified locked order ORD-8760.
    """
    supplier_row = conn.execute("SELECT id FROM users WHERE username = 'supplier_rajesh'").fetchone()
    nursery_row = conn.execute("SELECT id FROM users WHERE username = 'nursery_amit'").fetchone()
    if not supplier_row or not nursery_row:
        return

    supplier_id = supplier_row[0]
    nursery_id = nursery_row[0]

    ord_8760 = conn.execute("SELECT * FROM orders WHERE id = 'ORD-8760'").fetchone()
    insp_8760 = conn.execute("SELECT * FROM delivery_inspections WHERE order_id = 'ORD-8760'").fetchone()
    item_8760 = conn.execute("SELECT * FROM order_items WHERE order_id = 'ORD-8760'").fetchone()
    plant_row = conn.execute("SELECT * FROM plants WHERE id = ?", (item_8760['plant_id'],)).fetchone() if item_8760 and item_8760['plant_id'] else None

    if ord_8760 and insp_8760 and insp_8760['is_locked'] == 1 and item_8760:
        inv_id = "INV-2026-8760"
        inv_num = "INV-2026-8760"

        # Check if already seeded
        existing = conn.execute("SELECT id FROM invoices WHERE id = ?", (inv_id,)).fetchone()
        if existing:
            return

        sound_qty = insp_8760['sound_qty']
        unit_price = item_8760['unit_price']
        line_total = round(sound_qty * unit_price, 2)

        snapshot = json.dumps({
            "order_id": "ORD-8760",
            "invoice_number": inv_num,
            "supplier": {
                "id": supplier_id,
                "business_name": "GreenRoots Wholesale Farms",
                "email": "supplier@greenrootsfarms.com"
            },
            "nursery": {
                "id": nursery_id,
                "business_name": "Green Meadows Landscape Nursery",
                "email": "purchasing@greenmeadows.com"
            },
            "delivery_inspection": {
                "delivered_qty": insp_8760['delivered_qty'],
                "sound_qty": sound_qty,
                "damaged_qty": insp_8760['damaged_qty'],
                "damage_pct": insp_8760['damage_pct'],
                "locked_at": insp_8760['locked_at']
            },
            "billing_policy": "CREDITED_EXCLUDED",
            "damage_notes": "2 damaged units credited as agreed in deal terms."
        })

        conn.execute(
            """INSERT INTO invoices
               (id, invoice_number, order_id, supplier_user_id, nursery_user_id, inspection_id,
                invoice_date, due_date, currency, subtotal, tax_rate_pct, tax_amount, discount_amount,
                total_amount, total_quantity, status, damage_billing_policy, interest_rate_pct,
                interest_calculation_basis, interest_grace_period_days, agreement_ref, notes, terms_snapshot_json, created_by_user_id)
               VALUES (?, ?, ?, ?, ?, ?, '2026-10-16', '2026-10-26', 'INR', ?, 0.0, 0.0, 0.0, ?, ?, 'ISSUED', 'CREDITED_EXCLUDED', 18.0, 'ANNUAL_SIMPLE', 0, 'AGR-8760-v1', ?, ?, ?)""",
            (inv_id, inv_num, "ORD-8760", supplier_id, nursery_id, insp_8760['id'],
             line_total, line_total, sound_qty, "Commercial invoice issued based strictly on 98 verified sound plants. 2 transit-damaged plants credited.",
             snapshot, supplier_id)
        )

        conn.execute(
            """INSERT INTO invoice_items
               (invoice_id, order_item_id, plant_id, variety, botanical_name, category, container_size, unit,
                ordered_qty, delivered_qty, sound_qty, damaged_qty, billable_qty, unit_price, damaged_unit_price, line_total, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?)""",
            (inv_id, item_8760['id'], item_8760['plant_id'], item_8760['variety'],
             plant_row['botanical_name'] if plant_row else 'Epipremnum aureum',
             plant_row['category'] if plant_row else 'CLIMBER',
             plant_row['container_size'] if plant_row else '3-foot Totem Pole',
             plant_row['unit'] if plant_row else 'plant',
             item_8760['quantity'], insp_8760['delivered_qty'], sound_qty, insp_8760['damaged_qty'],
             sound_qty, unit_price, line_total, "2 totems damaged during transit credited at zero charge.")
        )

def ensure_invoices_seeded(conn):
    """
    Checks if invoices table has records; if empty, populates demo invoice.
    """
    try:
        count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        if count == 0:
            seed_invoices(conn)
    except sqlite3.OperationalError:
        pass


def ensure_payments_schema_updated(conn):
    """
    Phase 9 Non-destructive Migration:
    Creates payments and payment_allocations tables and indexes if they do not exist.
    """
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                payment_number TEXT UNIQUE NOT NULL,
                invoice_id TEXT NULL REFERENCES invoices(id),
                order_id TEXT NULL REFERENCES orders(id),
                supplier_user_id INTEGER NOT NULL REFERENCES users(id),
                nursery_user_id INTEGER NOT NULL REFERENCES users(id),
                amount REAL NOT NULL CHECK(amount > 0),
                unallocated_amount REAL NOT NULL DEFAULT 0.0 CHECK(unallocated_amount >= 0),
                payment_date TEXT NOT NULL,
                payment_method TEXT NOT NULL CHECK(payment_method IN ('BANK_TRANSFER', 'UPI', 'CHEQUE', 'CASH', 'OTHER')),
                reference_number TEXT NOT NULL,
                payment_type TEXT NOT NULL DEFAULT 'INVOICE_PAYMENT' CHECK(payment_type IN ('INVOICE_PAYMENT', 'ADVANCE_PAYMENT')),
                status TEXT NOT NULL DEFAULT 'RECORDED' CHECK(status IN ('RECORDED', 'REVERSED')),
                notes TEXT DEFAULT '',
                reversal_reason TEXT NULL,
                reversed_at DATETIME NULL,
                reversed_by_user_id INTEGER NULL REFERENCES users(id),
                created_by_user_id INTEGER NOT NULL REFERENCES users(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
                invoice_id TEXT NOT NULL REFERENCES invoices(id),
                amount REAL NOT NULL CHECK(amount > 0),
                status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'REVERSED')),
                notes TEXT DEFAULT '',
                allocated_by_user_id INTEGER NOT NULL REFERENCES users(id),
                allocated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_supplier ON payments(supplier_user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_nursery ON payments(nursery_user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_ref ON payments(reference_number);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_allocations_payment ON payment_allocations(payment_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_allocations_invoice ON payment_allocations(invoice_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_allocations_status ON payment_allocations(status);")
    except sqlite3.OperationalError:
        pass


def seed_payments(conn):
    """
    Phase 9 Demonstration Seed Data:
    Seeds initial advance payment for locked order ORD-8760 / invoice INV-2026-8760.
    In Deal Agreement AGR-8760-v1, a 25% advance of ₹10,500.00 was agreed.
    This creates:
    - Payment PAY-2026-8760 of ₹10,500.00 via Bank Transfer UTR982341092834
    - Direct allocation to INV-2026-8760
    - Leaves outstanding balance of ₹30,660.00 (₹41,160.00 - ₹10,500.00)
    """
    supplier_row = conn.execute("SELECT id FROM users WHERE username = 'supplier_rajesh'").fetchone()
    nursery_row = conn.execute("SELECT id FROM users WHERE username = 'nursery_amit'").fetchone()
    inv_8760 = conn.execute("SELECT * FROM invoices WHERE id = 'INV-2026-8760'").fetchone()

    if not supplier_row or not nursery_row or not inv_8760:
        return

    supplier_id = supplier_row[0]
    nursery_id = nursery_row[0]
    pay_id = "PAY-2026-8760"

    existing = conn.execute("SELECT id FROM payments WHERE id = ?", (pay_id,)).fetchone()
    if existing:
        return

    advance_amount = 10500.0

    conn.execute(
        """INSERT INTO payments
           (id, payment_number, invoice_id, order_id, supplier_user_id, nursery_user_id, amount,
            unallocated_amount, payment_date, payment_method, reference_number, payment_type,
            status, notes, created_by_user_id)
           VALUES (?, ?, ?, 'ORD-8760', ?, ?, ?, 0.0, '2026-10-10', 'BANK_TRANSFER', 'UTR982341092834',
                   'INVOICE_PAYMENT', 'RECORDED', ?, ?)""",
        (pay_id, pay_id, "INV-2026-8760", supplier_id, nursery_id, advance_amount,
         "25% advance payment settled via RTGS/NEFT as per Deal Agreement AGR-8760-v1.", supplier_id)
    )

    conn.execute(
        """INSERT INTO payment_allocations
           (payment_id, invoice_id, amount, status, notes, allocated_by_user_id)
           VALUES (?, ?, ?, 'ACTIVE', ?, ?)""",
        (pay_id, "INV-2026-8760", advance_amount, "Allocated to commercial invoice INV-2026-8760 upon issuance.", supplier_id)
    )


def ensure_payments_seeded(conn):
    try:
        count = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        if count == 0:
            seed_payments(conn)
    except sqlite3.OperationalError:
        pass

