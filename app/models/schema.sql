-- FloraChain B2B — SQLite Relational Schema
-- Phase 5 Plant Management: Wholesale Plant Catalog & Inventory

PRAGMA foreign_keys = ON;

-- 1. Users & Roles
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('SUPPLIER', 'NURSERY', 'ADMIN')),
    business_name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Wholesale Plant Orders
CREATE TABLE IF NOT EXISTS orders (
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
    loaded_at DATETIME NULL,
    loading_notes TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. Delivery Physical Inspections
CREATE TABLE IF NOT EXISTS delivery_inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE NOT NULL REFERENCES orders(id),
    delivered_qty INTEGER NOT NULL CHECK(delivered_qty >= 0),
    sound_qty INTEGER NOT NULL CHECK(sound_qty >= 0),
    damaged_qty INTEGER NOT NULL CHECK(damaged_qty >= 0),
    damage_pct REAL NOT NULL CHECK(damage_pct >= 0.0),
    damage_notes TEXT DEFAULT '',
    has_mismatch INTEGER NOT NULL CHECK(has_mismatch IN (0, 1)),
    mismatch_diff INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('DRAFT', 'PENDING_SUPPLIER_CONFIRMATION', 'LOCKED_VERIFIED', 'CORRECTED')),
    is_locked INTEGER NOT NULL DEFAULT 0 CHECK(is_locked IN (0, 1)),
    locked_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. Independent Party Counter-Signatures (Dual Confirmation)
CREATE TABLE IF NOT EXISTS inspection_confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER NOT NULL REFERENCES delivery_inspections(id) ON DELETE CASCADE,
    party_role TEXT NOT NULL CHECK(party_role IN ('NURSERY', 'SUPPLIER')),
    user_id INTEGER NOT NULL REFERENCES users(id),
    confirmed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT NOT NULL DEFAULT '127.0.0.1',
    signature_note TEXT DEFAULT '',
    CONSTRAINT uq_party_confirmation UNIQUE(inspection_id, party_role)
);

-- 5. Append-Only Audit Ledger
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    order_id TEXT NOT NULL,
    actor_user_id INTEGER REFERENCES users(id),
    actor_role TEXT NOT NULL,
    before_state_json TEXT NULL,
    after_state_json TEXT NOT NULL,
    justification TEXT DEFAULT '',
    ip_address TEXT NOT NULL DEFAULT '127.0.0.1',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 6. Administrative Corrections Workflow
CREATE TABLE IF NOT EXISTS inspection_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER NOT NULL REFERENCES delivery_inspections(id),
    requested_by INTEGER NOT NULL REFERENCES users(id),
    approved_by INTEGER NULL REFERENCES users(id),
    original_sound_qty INTEGER NOT NULL,
    original_damaged_qty INTEGER NOT NULL,
    corrected_sound_qty INTEGER NOT NULL,
    corrected_damaged_qty INTEGER NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME NULL
);

-- Indexes for performant lookup
CREATE INDEX IF NOT EXISTS idx_orders_supplier ON orders(supplier_user_id);
CREATE INDEX IF NOT EXISTS idx_orders_nursery ON orders(nursery_user_id);
CREATE INDEX IF NOT EXISTS idx_confirmations_insp ON inspection_confirmations(inspection_id);
CREATE INDEX IF NOT EXISTS idx_audit_order ON audit_events(order_id);

-- 7. Wholesale Plant Catalog & Inventory
CREATE TABLE IF NOT EXISTS plants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    common_name TEXT NOT NULL,
    botanical_name TEXT DEFAULT '',
    category TEXT NOT NULL CHECK(category IN (
        'INDOOR', 'OUTDOOR', 'FLOWERING', 'ORNAMENTAL',
        'TREE', 'PALM', 'SUCCULENT', 'CLIMBER',
        'SEASONAL', 'MEDICINAL', 'FRUIT', 'OTHER'
    )),
    container_size TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT 'plant' CHECK(unit IN ('plant', 'tray', 'bag', 'pot', 'bundle')),
    unit_price REAL NOT NULL CHECK(unit_price > 0),
    stock_qty INTEGER NOT NULL DEFAULT 0 CHECK(stock_qty >= 0),
    min_order_qty INTEGER NOT NULL DEFAULT 1 CHECK(min_order_qty >= 1),
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'DISCONTINUED', 'OUT_OF_STOCK')),
    supplier_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plants_supplier ON plants(supplier_user_id);
CREATE INDEX IF NOT EXISTS idx_plants_category ON plants(category);
CREATE INDEX IF NOT EXISTS idx_plants_status ON plants(status);

-- 8. Digital Deal Agreements & Payment Terms (formerly section 7)
CREATE TABLE IF NOT EXISTS deal_agreements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agreement_ref TEXT UNIQUE NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(id),
    version INTEGER NOT NULL DEFAULT 1,
    supplier_user_id INTEGER NOT NULL REFERENCES users(id),
    nursery_user_id INTEGER NOT NULL REFERENCES users(id),
    plant_variety TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price > 0),
    total_order_value REAL NOT NULL CHECK(total_order_value > 0),
    advance_percentage REAL NOT NULL CHECK(advance_percentage >= 0 AND advance_percentage <= 100),
    advance_amount REAL NOT NULL CHECK(advance_amount >= 0),
    balance_amount REAL NOT NULL CHECK(balance_amount >= 0),
    payment_due_date TEXT NOT NULL,
    payment_period_days INTEGER DEFAULT 10 CHECK(payment_period_days >= 0),
    interest_rate_pct REAL NOT NULL DEFAULT 0.0 CHECK(interest_rate_pct >= 0),
    interest_calculation_basis TEXT DEFAULT 'ANNUAL_SIMPLE' CHECK(interest_calculation_basis IN ('ANNUAL_SIMPLE', 'MONTHLY_SIMPLE', 'DAILY_SIMPLE', 'NONE')),
    interest_grace_period_days INTEGER DEFAULT 0 CHECK(interest_grace_period_days >= 0),
    notes TEXT DEFAULT '',
    status TEXT NOT NULL CHECK(status IN ('DRAFT', 'PENDING_COUNTERPARTY_APPROVAL', 'AGREED', 'CANCELLED')),
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    agreed_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 9. Independent Party Approvals for Deal Agreements (formerly section 8)
CREATE TABLE IF NOT EXISTS agreement_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agreement_id INTEGER NOT NULL REFERENCES deal_agreements(id) ON DELETE CASCADE,
    party_role TEXT NOT NULL CHECK(party_role IN ('SUPPLIER', 'NURSERY')),
    user_id INTEGER NOT NULL REFERENCES users(id),
    approval_type TEXT NOT NULL DEFAULT 'IN_APP_CLICK' CHECK(approval_type IN ('IN_APP_CLICK', 'RECORDED_CONSENT')),
    terms_snapshot_json TEXT NOT NULL,
    notes TEXT DEFAULT '',
    approved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT NOT NULL DEFAULT '127.0.0.1',
    CONSTRAINT uq_agreement_party UNIQUE(agreement_id, party_role)
);

CREATE INDEX IF NOT EXISTS idx_deal_agreements_order ON deal_agreements(order_id);
CREATE INDEX IF NOT EXISTS idx_deal_agreements_supplier ON deal_agreements(supplier_user_id);
CREATE INDEX IF NOT EXISTS idx_deal_agreements_nursery ON deal_agreements(nursery_user_id);
CREATE INDEX IF NOT EXISTS idx_agreement_approvals_agr ON agreement_approvals(agreement_id);

-- 10. Order Line Items (Wholesale Plant Items per Order)
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    plant_id INTEGER REFERENCES plants(id),
    variety TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price > 0),
    line_total REAL NOT NULL CHECK(line_total > 0),
    loaded_qty INTEGER NOT NULL DEFAULT 0 CHECK(loaded_qty >= 0 AND loaded_qty <= quantity),
    delivered_qty INTEGER NULL,
    sound_qty INTEGER NULL,
    damaged_qty INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_plant ON order_items(plant_id);

-- 11. Wholesale Invoices (Phase 8: Verified Delivery Invoicing)
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
    interest_rate_pct REAL NOT NULL DEFAULT 0.0 CHECK(interest_rate_pct >= 0),
    interest_calculation_basis TEXT NOT NULL DEFAULT 'ANNUAL_SIMPLE' CHECK(interest_calculation_basis IN ('ANNUAL_SIMPLE', 'MONTHLY_SIMPLE', 'DAILY_SIMPLE', 'NONE')),
    interest_grace_period_days INTEGER NOT NULL DEFAULT 0 CHECK(interest_grace_period_days >= 0),
    agreement_ref TEXT NULL,
    notes TEXT DEFAULT '',
    terms_snapshot_json TEXT NULL,
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_invoices_order ON invoices(order_id);
CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_user_id);
CREATE INDEX IF NOT EXISTS idx_invoices_nursery ON invoices(nursery_user_id);
CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoices_due ON invoices(due_date);

-- 12. Wholesale Invoice Line Items (Frozen Snapshot of Invoiced Plant Varieties)
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

CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_plant ON invoice_items(plant_id);

-- 13. Wholesale Payments (Phase 9: Payment Management)
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

CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_supplier ON payments(supplier_user_id);
CREATE INDEX IF NOT EXISTS idx_payments_nursery ON payments(nursery_user_id);
CREATE INDEX IF NOT EXISTS idx_payments_ref ON payments(reference_number);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

-- 14. Payment Allocations (Phase 9: Settlement to Invoices)
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

CREATE INDEX IF NOT EXISTS idx_allocations_payment ON payment_allocations(payment_id);
CREATE INDEX IF NOT EXISTS idx_allocations_invoice ON payment_allocations(invoice_id);
CREATE INDEX IF NOT EXISTS idx_allocations_status ON payment_allocations(status);
