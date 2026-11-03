"""
FloraChain B2B — Phase 14 Stage 3: Live PostgreSQL Inspection and Reporting Script
"""

import os
import sys
from decimal import Decimal

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import dotenv
import psycopg2
from app.models.database import parse_pg_url

dotenv.load_dotenv(os.path.join(BASE_DIR, '.env'))
params = parse_pg_url(os.getenv('TEST_DATABASE_URL'))
conn = psycopg2.connect(**params)
cur = conn.cursor()

tables = [
    'users', 'plants', 'orders', 'order_items', 'delivery_inspections',
    'inspection_confirmations', 'deal_agreements', 'agreement_approvals',
    'invoices', 'invoice_items', 'payments', 'payment_allocations',
    'audit_events', 'inspection_corrections'
]

print("=== TABLE ROW COUNTS IN POSTGRESQL (florachain_test) ===")
total = 0
for t in tables:
    cur.execute(f"SELECT count(*) FROM {t}")
    cnt = cur.fetchone()[0]
    total += cnt
    print(f"  - {t:26}: {cnt:>3} rows")
print(f"  TOTAL ROWS                : {total:>3} rows")

print("\n=== FINANCIAL TOTALS IN POSTGRESQL ===")
cur.execute("SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE status = 'ISSUED'")
invoiced = float(cur.fetchone()[0])
print(f"  - Gross Invoiced (ISSUED)   : Rs. {invoiced:,.2f}")

cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'RECORDED'")
payments = float(cur.fetchone()[0])
print(f"  - Recorded Payments         : Rs. {payments:,.2f}")

cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payment_allocations WHERE status = 'ACTIVE'")
allocations = float(cur.fetchone()[0])
print(f"  - Active Allocations        : Rs. {allocations:,.2f}")

print("\n=== PRIMARY KEY SAMPLES ===")
cur.execute("SELECT id, username, role FROM users ORDER BY id")
print("  Users      :", cur.fetchall())

cur.execute("SELECT id, variety FROM orders ORDER BY id")
print("  Orders     :", cur.fetchall())

cur.execute("SELECT invoice_number, total_amount, due_date FROM invoices ORDER BY id")
print("  Invoices   :", cur.fetchall())

cur.execute("SELECT payment_number, amount, payment_method FROM payments ORDER BY id")
print("  Payments   :", cur.fetchall())

cur.execute("SELECT agreement_ref, plant_variety, interest_rate_pct FROM deal_agreements ORDER BY id")
print("  Agreements :", cur.fetchall())

print("\n=== ADVANCED IDENTITY SEQUENCES ===")
for t in ['users', 'plants', 'order_items', 'delivery_inspections', 'deal_agreements', 'audit_events']:
    cur.execute(f"SELECT last_value FROM pg_sequences WHERE sequencename = '{t}_id_seq'")
    r = cur.fetchone()
    print(f"  {t}_id_seq last_value:", r[0] if r else 'N/A')

cur.close()
conn.close()

