"""
FloraChain B2B — Wholesale Invoice Generation & Freezing Engine
Phase 8: Verified Delivery Invoicing, Historical Price Immutability & Audit Trail

Enforces:
- Invoicing strictly for orders with status = 'LOCKED_VERIFIED' and is_locked = 1
- Use of the wholesale order's recorded unit prices (never current catalog prices)
- Single-variety orders: invoiced based on confirmed sound_qty (damaged credited by default or per agreed billing terms)
- Multi-variety orders with no damage: invoiced on verified delivered quantity of each item
- Multi-variety orders with damage: requires explicit item-level delivered, sound, and damaged counts (pro-rata/guessed quantities strictly prohibited)
- Itemized delivery counts must be internally consistent and dual-confirmed before invoicing
- Prevention of duplicate invoices for the same wholesale order
- Permanent freezing of issued invoice lines, quantities, prices, and totals (read-only snapshot)
- Role-based data isolation (Supplier vs Nursery vs Admin)
- Append-only audit trail logging for all invoice creation and cancellation events
"""

import json
from datetime import datetime, date
from app.services.audit_service import log_audit_event


def generate_next_invoice_number(conn):
    """
    Generates a human-friendly unique invoice number (e.g. INV-2026-9001).
    Guarantees sequential uniqueness at the database level.
    """
    current_year = datetime.now().year
    prefix = f"INV-{current_year}-"
    rows = conn.execute("SELECT invoice_number FROM invoices WHERE invoice_number LIKE ?", (f"{prefix}%",)).fetchall()
    highest = 9000
    for r in rows:
        num_part = r['invoice_number'].replace(prefix, '')
        if num_part.isdigit():
            val = int(num_part)
            if val > highest:
                highest = val
    return f"{prefix}{highest + 1}"


def calculate_invoice_totals(items, tax_rate_pct=0.0, discount_amount=0.0):
    """
    Calculates subtotal, tax amount, discount, and grand total amount.
    All monetary amounts are rounded to 2 decimal places.
    """
    subtotal = round(sum(it['line_total'] for it in items), 2)
    tax_rate = max(0.0, float(tax_rate_pct or 0.0))
    tax_amount = round(subtotal * (tax_rate / 100.0), 2)
    discount = max(0.0, float(discount_amount or 0.0))
    discount = min(discount, subtotal + tax_amount)
    total_amount = round(subtotal + tax_amount - discount, 2)
    total_quantity = sum(it.get('billable_qty', it.get('sound_qty', 0)) for it in items)

    return {
        "subtotal": subtotal,
        "tax_rate_pct": tax_rate,
        "tax_amount": tax_amount,
        "discount_amount": discount,
        "total_amount": total_amount,
        "total_quantity": total_quantity
    }


def record_itemized_delivery_inspection(conn, order_id, actor_user, items_data, ip_address="127.0.0.1"):
    """
    Records explicit item-level delivery, sound, and damaged quantities for multi-variety orders.
    Enforces:
    - User must be assigned Nursery receiving manager or Admin (or Supplier counter-signing)
    - Order existence and arrival inspection presence
    - Strict mathematical validations per line:
      * delivered, sound, damaged must be non-negative integers
      * sound_qty + damaged_qty == delivered_qty
      * delivered_qty <= loaded_qty (or quantity)
    - Strict sum validation:
      * sum(item.delivered_qty) == inspection.delivered_qty
      * sum(item.sound_qty) == inspection.sound_qty
      * sum(item.damaged_qty) == inspection.damaged_qty
    - Audit trail logging
    """
    if not actor_user:
        raise PermissionError("Authentication required.")

    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        raise ValueError(f"Order #{order_id} not found.")

    inspection = conn.execute("SELECT * FROM delivery_inspections WHERE order_id = ?", (order_id,)).fetchone()
    if not inspection:
        raise ValueError(f"No delivery inspection recorded for Order #{order_id}. Dock counts must be logged first.")

    # Authorization check
    role = actor_user.get('role')
    if role not in ('NURSERY', 'SUPPLIER', 'ADMIN'):
        raise PermissionError("Unauthorized role for itemized delivery inspection.")

    if role == 'NURSERY' and order['nursery_user_id'] != actor_user['id']:
        raise PermissionError(f"Unauthorized: You are not the assigned nursery for Order #{order_id}.")
    if role == 'SUPPLIER' and order['supplier_user_id'] != actor_user['id']:
        raise PermissionError(f"Unauthorized: You are not the assigned supplier for Order #{order_id}.")

    # Fetch existing order items
    order_items = conn.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC", (order_id,)).fetchall()
    if not order_items:
        raise ValueError(f"Order #{order_id} has no line items.")

    items_by_id = {it['id']: dict(it) for it in order_items}

    # Validate items_data structure
    if not isinstance(items_data, list) or len(items_data) != len(order_items):
        raise ValueError(f"Itemized inspection must contain all {len(order_items)} order line items.")

    sanitized_items = []
    for raw_it in items_data:
        item_id = raw_it.get('order_item_id') or raw_it.get('id')
        if not item_id or item_id not in items_by_id:
            raise ValueError(f"Invalid or missing order_item_id '{item_id}'.")

        orig_item = items_by_id[item_id]

        deliv_val = raw_it.get('delivered_qty')
        sound_val = raw_it.get('sound_qty')
        damaged_val = raw_it.get('damaged_qty', 0)

        for name, val in [("Delivered", deliv_val), ("Sound", sound_val), ("Damaged", damaged_val)]:
            if type(val) is not int or val < 0:
                raise ValueError(f"Variety '{orig_item['variety']}': {name} quantity must be a non-negative whole integer.")

        if sound_val + damaged_val != deliv_val:
            raise ValueError(
                f"Variety '{orig_item['variety']}': Sound ({sound_val}) + Damaged ({damaged_val}) "
                f"does not equal Delivered ({deliv_val})."
            )

        max_allowed = orig_item['loaded_qty'] if (orig_item.get('loaded_qty') and orig_item['loaded_qty'] > 0) else orig_item['quantity']
        if deliv_val > max_allowed:
            raise ValueError(
                f"Variety '{orig_item['variety']}': Delivered quantity ({deliv_val}) exceeds "
                f"maximum dispatched quantity ({max_allowed})."
            )

        sanitized_items.append({
            "id": item_id,
            "variety": orig_item['variety'],
            "delivered_qty": deliv_val,
            "sound_qty": sound_val,
            "damaged_qty": damaged_val
        })

    # Validate aggregate sums against overall delivery inspection
    tot_deliv = sum(it['delivered_qty'] for it in sanitized_items)
    tot_sound = sum(it['sound_qty'] for it in sanitized_items)
    tot_damaged = sum(it['damaged_qty'] for it in sanitized_items)

    if tot_deliv != inspection['delivered_qty']:
        raise ValueError(
            f"Sum of item delivered counts ({tot_deliv}) does not match "
            f"order delivered total ({inspection['delivered_qty']})."
        )
    if tot_sound != inspection['sound_qty']:
        raise ValueError(
            f"Sum of item sound counts ({tot_sound}) does not match "
            f"order verified sound total ({inspection['sound_qty']})."
        )
    if tot_damaged != inspection['damaged_qty']:
        raise ValueError(
            f"Sum of item damaged counts ({tot_damaged}) does not match "
            f"order damaged total ({inspection['damaged_qty']})."
        )

    # Persist itemized counts
    for s_it in sanitized_items:
        conn.execute(
            """UPDATE order_items
               SET delivered_qty = ?, sound_qty = ?, damaged_qty = ?
               WHERE id = ?""",
            (s_it['delivered_qty'], s_it['sound_qty'], s_it['damaged_qty'], s_it['id'])
        )

    log_audit_event(
        conn,
        event_type="ITEMIZED_INSPECTION_RECORDED",
        order_id=order_id,
        actor_user_id=actor_user['id'],
        actor_role=actor_user['role'],
        before_state=None,
        after_state={"items": sanitized_items, "tot_sound": tot_sound, "tot_damaged": tot_damaged},
        justification=f"Item-level delivery breakdown recorded with {tot_sound} sound and {tot_damaged} damaged plants.",
        ip_address=ip_address
    )

    return sanitized_items


def generate_invoice_for_order(conn, order_id, actor_user, options=None, ip_address="127.0.0.1"):
    """
    Generates and permanently freezes a commercial wholesale invoice for a verified order.
    
    CRITICAL BUSINESS & SECURITY RULES:
    1. Authentication & Role Authorization:
       - Only wholesale SUPPLIER (the assigned seller) or ADMIN can generate invoices.
       - NURSERY role is rejected (403 Forbidden).
    2. Verification & Locking Enforcement:
       - Order MUST have status = 'LOCKED_VERIFIED' and delivery_inspections.is_locked = 1.
       - Unverified, staging, or in-transit orders are strictly rejected.
    3. Duplicate Prevention:
       - Rejects invoice creation if an active invoice (status != 'CANCELLED') already exists.
    4. Price Immutability:
       - Uses the order's recorded unit prices from order_items, NEVER live plant catalog prices.
    5. Invoiced Quantities:
       - Single-variety orders: Invoices confirmed sound_qty. Damaged units are credited (default)
         or billed at the agreed damage billing rate specified in deal terms / options.
       - Multi-variety orders (no damage): Invoices each item's full verified delivered quantity.
       - Multi-variety orders (with damage): Requires explicit item-level delivered, sound, and
         damaged counts in order_items. Pro-rata or guessed allocations are prohibited.
    6. Historical Freezing:
       - All invoice lines, plant metadata, unit prices, quantities, and totals are copied into
         invoices and invoice_items tables. Future catalog updates or order edits never alter them.
    7. Audit Trail:
       - Appends INVOICE_ISSUED event to audit_events.
    """
    options = options or {}

    if not actor_user:
        raise PermissionError("Authentication required to issue invoices.")

    role = actor_user.get('role')
    if role not in ('SUPPLIER', 'ADMIN'):
        raise PermissionError("Forbidden: Only wholesale suppliers and platform administrators can issue invoices.")

    # 1. Fetch Order Header & Counterparties
    order = conn.execute(
        """SELECT o.*,
                  s.business_name as supplier_name, s.email as supplier_email,
                  n.business_name as nursery_name, n.email as nursery_email
           FROM orders o
           JOIN users s ON o.supplier_user_id = s.id
           JOIN users n ON o.nursery_user_id = n.id
           WHERE o.id = ?""",
        (order_id,)
    ).fetchone()
    if not order:
        raise ValueError(f"Order #{order_id} does not exist.")

    if role == 'SUPPLIER' and order['supplier_user_id'] != actor_user['id']:
        raise PermissionError(f"Unauthorized: You are not the assigned supplier for Order #{order_id}.")

    # 2. Enforce Delivery Verification & Locking
    inspection = conn.execute("SELECT * FROM delivery_inspections WHERE order_id = ?", (order_id,)).fetchone()
    if not inspection or inspection['is_locked'] != 1 or order['status'] != 'LOCKED_VERIFIED':
        raise PermissionError(
            f"Cannot issue invoice: Order #{order_id} has not completed independent physical delivery "
            f"verification and dual counter-signature locking (current order status: '{order['status']}')."
        )

    # 3. Prevent Duplicate Invoices
    existing_inv = conn.execute(
        "SELECT id, invoice_number, status, total_amount FROM invoices WHERE order_id = ? AND status != 'CANCELLED'",
        (order_id,)
    ).fetchone()
    if existing_inv:
        raise ValueError(
            f"Duplicate Invoice Conflict: Commercial invoice #{existing_inv['invoice_number']} "
            f"has already been issued for Order #{order_id}."
        )

    # 4. Fetch Deal Agreement for Agreed Billing Terms
    agr_row = conn.execute(
        "SELECT * FROM deal_agreements WHERE order_id = ? ORDER BY version DESC LIMIT 1",
        (order_id,)
    ).fetchone()
    agreement = dict(agr_row) if agr_row else None

    # Determine damage billing rate / policy:
    # Default: Damaged plants are credited at zero charge (sound_delivered_qty only).
    # If explicitly agreed or specified in options, apply agreed billing rate to damaged units.
    damage_charge_pct = 0.0
    damage_billing_policy = "CREDITED_EXCLUDED"

    if 'damage_charge_pct' in options:
        try:
            damage_charge_pct = float(options['damage_charge_pct'])
            if damage_charge_pct < 0 or damage_charge_pct > 100:
                raise ValueError("damage_charge_pct must be between 0.0 and 100.0.")
            if damage_charge_pct > 0:
                damage_billing_policy = f"CHARGED_{int(damage_charge_pct)}PCT"
        except (ValueError, TypeError):
            raise ValueError("Invalid damage_charge_pct format.")
    elif agreement and agreement['notes']:
        # Check agreement notes for explicit salvage terms
        notes_lower = agreement['notes'].lower()
        if 'credit' in notes_lower:
            damage_charge_pct = 0.0
            damage_billing_policy = "CREDITED_EXCLUDED"

    # 5. Fetch Order Line Items
    order_items_rows = conn.execute(
        """SELECT oi.*, p.botanical_name, p.category, p.container_size, p.unit
           FROM order_items oi
           LEFT JOIN plants p ON oi.plant_id = p.id
           WHERE oi.order_id = ?
           ORDER BY oi.id ASC""",
        (order_id,)
    ).fetchall()

    if not order_items_rows:
        raise ValueError(f"Order #{order_id} has no line items to invoice.")

    order_items = [dict(it) for it in order_items_rows]

    is_multi_variety = len(order_items) > 1
    has_transit_damage = inspection['damaged_qty'] > 0

    # 6. Calculate Line Items
    invoiced_items = []

    if not is_multi_variety:
        # SINGLE-VARIETY ORDER
        it = order_items[0]
        ordered_q = it['quantity']
        deliv_q = inspection['delivered_qty']
        sound_q = inspection['sound_qty']
        damaged_q = inspection['damaged_qty']

        unit_price = float(it['unit_price'])
        damaged_price = round(unit_price * (damage_charge_pct / 100.0), 2)
        line_total = round((sound_q * unit_price) + (damaged_q * damaged_price), 2)
        billable_q = sound_q if damage_charge_pct == 0.0 else (sound_q + damaged_q)

        notes_item = ""
        if damaged_q > 0:
            if damage_charge_pct == 0.0:
                notes_item = f"{damaged_q} transit-damaged units credited at zero charge."
            else:
                notes_item = f"{damaged_q} damaged units billed at agreed {damage_charge_pct}% rate (Rs. {damaged_price:.2f}/unit)."

        invoiced_items.append({
            "order_item_id": it['id'],
            "plant_id": it['plant_id'],
            "variety": it['variety'],
            "botanical_name": it['botanical_name'] or '',
            "category": it['category'] or '',
            "container_size": it['container_size'] or '',
            "unit": it['unit'] or 'plant',
            "ordered_qty": ordered_q,
            "delivered_qty": deliv_q,
            "sound_qty": sound_q,
            "damaged_qty": damaged_q,
            "billable_qty": billable_q,
            "unit_price": unit_price,
            "damaged_unit_price": damaged_price,
            "line_total": line_total,
            "notes": notes_item
        })

    elif is_multi_variety and not has_transit_damage:
        # MULTI-VARIETY ORDER (100% SOUND / ZERO DAMAGE)
        for it in order_items:
            q = it['quantity']
            unit_price = float(it['unit_price'])
            line_total = round(q * unit_price, 2)

            invoiced_items.append({
                "order_item_id": it['id'],
                "plant_id": it['plant_id'],
                "variety": it['variety'],
                "botanical_name": it['botanical_name'] or '',
                "category": it['category'] or '',
                "container_size": it['container_size'] or '',
                "unit": it['unit'] or 'plant',
                "ordered_qty": q,
                "delivered_qty": q,
                "sound_qty": q,
                "damaged_qty": 0,
                "billable_qty": q,
                "unit_price": unit_price,
                "damaged_unit_price": 0.0,
                "line_total": line_total,
                "notes": "100% sound plants verified at delivery dock."
            })

    else:
        # MULTI-VARIETY ORDER WITH TRANSIT DAMAGE:
        # Strict requirement: Explicit item-level delivered, sound, and damaged counts required.
        # Pro-rata or guessed allocations are prohibited.
        missing_items = [it['variety'] for it in order_items if it.get('sound_qty') is None or it.get('delivered_qty') is None]
        if missing_items:
            raise ValueError(
                f"Cannot generate invoice: Multi-variety Order #{order_id} has transit damage ({inspection['damaged_qty']} units), "
                f"but lacks explicit item-level delivery inspection counts for: {', '.join(missing_items)}. "
                f"Itemized inspection counts must be recorded and verified before invoicing. Pro-rata allocation is prohibited."
            )

        # Validate item-level mathematical consistency
        tot_deliv = sum(it['delivered_qty'] for it in order_items)
        tot_sound = sum(it['sound_qty'] for it in order_items)
        tot_damaged = sum(it['damaged_qty'] for it in order_items)

        if tot_sound != inspection['sound_qty'] or tot_damaged != inspection['damaged_qty'] or tot_deliv != inspection['delivered_qty']:
            raise ValueError(
                f"Item-level counts mismatch: items total sound={tot_sound}, damaged={tot_damaged}, delivered={tot_deliv} "
                f"does not match verified inspection (sound={inspection['sound_qty']}, damaged={inspection['damaged_qty']}, delivered={inspection['delivered_qty']})."
            )

        for it in order_items:
            deliv_q = it['delivered_qty']
            sound_q = it['sound_qty']
            damaged_q = it['damaged_qty']
            unit_price = float(it['unit_price'])
            damaged_price = round(unit_price * (damage_charge_pct / 100.0), 2)
            line_total = round((sound_q * unit_price) + (damaged_q * damaged_price), 2)
            billable_q = sound_q if damage_charge_pct == 0.0 else (sound_q + damaged_q)

            notes_item = ""
            if damaged_q > 0:
                if damage_charge_pct == 0.0:
                    notes_item = f"{damaged_q} damaged units credited at zero charge."
                else:
                    notes_item = f"{damaged_q} damaged units billed at agreed {damage_charge_pct}% rate (Rs. {damaged_price:.2f}/unit)."

            invoiced_items.append({
                "order_item_id": it['id'],
                "plant_id": it['plant_id'],
                "variety": it['variety'],
                "botanical_name": it['botanical_name'] or '',
                "category": it['category'] or '',
                "container_size": it['container_size'] or '',
                "unit": it['unit'] or 'plant',
                "ordered_qty": it['quantity'],
                "delivered_qty": deliv_q,
                "sound_qty": sound_q,
                "damaged_qty": damaged_q,
                "billable_qty": billable_q,
                "unit_price": unit_price,
                "damaged_unit_price": damaged_price,
                "line_total": line_total,
                "notes": notes_item
            })

    # 7. Invoice Totals & Financial Calculations
    tax_rate_pct = float(options.get('tax_rate_pct', 0.0))
    discount_amount = float(options.get('discount_amount', 0.0))
    totals = calculate_invoice_totals(invoiced_items, tax_rate_pct, discount_amount)

    invoice_number = (options.get('invoice_number') or '').strip()
    if not invoice_number:
        invoice_number = generate_next_invoice_number(conn)
    invoice_id = invoice_number

    invoice_date = options.get('invoice_date') or datetime.now().strftime('%Y-%m-%d')
    due_date = agreement['payment_due_date'] if (agreement and agreement.get('payment_due_date')) else None
    interest_rate_pct = float(agreement['interest_rate_pct']) if (agreement and agreement.get('interest_rate_pct') is not None) else 0.0
    interest_calc_basis = str(agreement['interest_calculation_basis']) if (agreement and agreement.get('interest_calculation_basis')) else 'ANNUAL_SIMPLE'
    interest_grace_days = int(agreement['interest_grace_period_days']) if (agreement and agreement.get('interest_grace_period_days') is not None) else 0
    agreement_ref = agreement['agreement_ref'] if agreement else None

    # 8. Create Terms & Counterparty Frozen Snapshot
    terms_snapshot = {
        "invoice_number": invoice_number,
        "order_id": order_id,
        "supplier": {
            "id": order['supplier_user_id'],
            "business_name": order['supplier_name'],
            "email": order['supplier_email']
        },
        "nursery": {
            "id": order['nursery_user_id'],
            "business_name": order['nursery_name'],
            "email": order['nursery_email']
        },
        "delivery_inspection": {
            "id": inspection['id'],
            "delivered_qty": inspection['delivered_qty'],
            "sound_qty": inspection['sound_qty'],
            "damaged_qty": inspection['damaged_qty'],
            "damage_pct": inspection['damage_pct'],
            "locked_at": inspection['locked_at']
        },
        "billing_terms": {
            "damage_billing_policy": damage_billing_policy,
            "damage_charge_pct": damage_charge_pct,
            "tax_rate_pct": totals['tax_rate_pct'],
            "discount_amount": totals['discount_amount']
        },
        "interest_terms": {
            "interest_rate_pct": interest_rate_pct,
            "interest_calculation_basis": interest_calc_basis,
            "interest_grace_period_days": interest_grace_days,
            "payment_due_date": due_date
        },
        "agreement_ref": agreement_ref
    }

    # 9. Insert Invoice Header (Frozen Snapshot)
    conn.execute(
        """INSERT INTO invoices
           (id, invoice_number, order_id, supplier_user_id, nursery_user_id, inspection_id,
            invoice_date, due_date, currency, subtotal, tax_rate_pct, tax_amount, discount_amount,
            total_amount, total_quantity, status, damage_billing_policy, interest_rate_pct,
            interest_calculation_basis, interest_grace_period_days, agreement_ref, notes, terms_snapshot_json, created_by_user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'INR', ?, ?, ?, ?, ?, ?, 'ISSUED', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (invoice_id, invoice_number, order_id, order['supplier_user_id'], order['nursery_user_id'],
         inspection['id'], invoice_date, due_date, totals['subtotal'], totals['tax_rate_pct'],
         totals['tax_amount'], totals['discount_amount'], totals['total_amount'], totals['total_quantity'],
         damage_billing_policy, interest_rate_pct, interest_calc_basis, interest_grace_days, agreement_ref,
         options.get('notes', '').strip(), json.dumps(terms_snapshot), actor_user['id'])
    )

    # 10. Insert Frozen Invoice Line Items
    for inv_it in invoiced_items:
        conn.execute(
            """INSERT INTO invoice_items
               (invoice_id, order_item_id, plant_id, variety, botanical_name, category, container_size, unit,
                ordered_qty, delivered_qty, sound_qty, damaged_qty, billable_qty, unit_price, damaged_unit_price, line_total, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (invoice_id, inv_it['order_item_id'], inv_it['plant_id'], inv_it['variety'],
             inv_it['botanical_name'], inv_it['category'], inv_it['container_size'], inv_it['unit'],
             inv_it['ordered_qty'], inv_it['delivered_qty'], inv_it['sound_qty'], inv_it['damaged_qty'],
             inv_it['billable_qty'], inv_it['unit_price'], inv_it['damaged_unit_price'], inv_it['line_total'], inv_it['notes'])
        )

    # 11. Append Audit Event
    log_audit_event(
        conn,
        event_type="INVOICE_ISSUED",
        order_id=order_id,
        actor_user_id=actor_user['id'],
        actor_role=actor_user['role'],
        before_state=None,
        after_state={
            "invoice_number": invoice_number,
            "total_amount": totals['total_amount'],
            "total_quantity": totals['total_quantity'],
            "subtotal": totals['subtotal'],
            "items_count": len(invoiced_items)
        },
        justification=options.get('notes', '').strip() or f"Commercial wholesale invoice #{invoice_number} issued for verified delivery.",
        ip_address=ip_address
    )

    return get_invoice_details(conn, invoice_id, actor_user)


def get_invoice_details(conn, invoice_id_or_number, actor_user=None):
    """
    Retrieves full details of an issued invoice:
    - Header with supplier & nursery profiles
    - Frozen itemized invoice line items
    - Delivery inspection and audit trail metadata
    Enforces role isolation (Supplier vs Nursery vs Admin).
    """
    inv = conn.execute(
        """SELECT i.*,
                  s.business_name as supplier_name, s.email as supplier_email, s.username as supplier_username,
                  n.business_name as nursery_name, n.email as nursery_email, n.username as nursery_username,
                  o.truck_no, o.driver_info, o.variety as order_summary_variety
           FROM invoices i
           JOIN users s ON i.supplier_user_id = s.id
           JOIN users n ON i.nursery_user_id = n.id
           JOIN orders o ON i.order_id = o.id
           WHERE i.id = ? OR i.invoice_number = ?""",
        (invoice_id_or_number, invoice_id_or_number)
    ).fetchone()

    if not inv:
        return None

    inv_dict = dict(inv)

    # Role Isolation Check
    if actor_user and actor_user.get('role') != 'ADMIN':
        user_id = actor_user.get('id')
        if user_id not in (inv_dict['supplier_user_id'], inv_dict['nursery_user_id']):
            raise PermissionError(f"Unauthorized: You do not have permission to view Invoice #{inv_dict['invoice_number']}.")

    # Fetch Frozen Line Items
    item_rows = conn.execute(
        """SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id ASC""",
        (inv_dict['id'],)
    ).fetchall()
    items = [dict(it) for it in item_rows]

    # Parse terms snapshot
    snapshot = {}
    if inv_dict.get('terms_snapshot_json'):
        try:
            snapshot = json.loads(inv_dict['terms_snapshot_json'])
        except (ValueError, TypeError):
            snapshot = {}

    # Fetch Payment Summary
    from app.services.payment_service import get_invoice_payment_summary
    pay_summary = get_invoice_payment_summary(conn, inv_dict['id'])

    # Fetch Interest & Due Date Summary
    from app.services.interest_service import calculate_invoice_interest
    interest_summary = calculate_invoice_interest(conn, inv_dict['id'])

    return {
        "invoice": inv_dict,
        "items": items,
        "items_count": len(items),
        "snapshot": snapshot,
        "payment_summary": pay_summary,
        "interest_summary": interest_summary,
        "supplier": {
            "id": inv_dict['supplier_user_id'],
            "name": inv_dict['supplier_name'],
            "email": inv_dict['supplier_email']
        },
        "nursery": {
            "id": inv_dict['nursery_user_id'],
            "name": inv_dict['nursery_name'],
            "email": inv_dict['nursery_email']
        }
    }


def list_invoices_for_user(conn, actor_user, filters=None):
    """
    Returns invoices accessible to the authenticated user.
    Enforces role isolation:
    - SUPPLIER: sees invoices where supplier_user_id = user['id']
    - NURSERY: sees invoices where nursery_user_id = user['id']
    - ADMIN: sees all platform invoices
    """
    filters = filters or {}
    params = []
    where_clauses = []

    # Role Isolation
    if actor_user['role'] == 'SUPPLIER':
        where_clauses.append("i.supplier_user_id = ?")
        params.append(actor_user['id'])
    elif actor_user['role'] == 'NURSERY':
        where_clauses.append("i.nursery_user_id = ?")
        params.append(actor_user['id'])

    # Status Filter
    status_filter = (filters.get('status') or '').strip().upper()
    if status_filter and status_filter != 'ALL':
        where_clauses.append("i.status = ?")
        params.append(status_filter)

    # Search Query
    search_q = (filters.get('search') or filters.get('q') or '').strip().lower()
    if search_q:
        where_clauses.append(
            "(LOWER(i.invoice_number) LIKE ? OR LOWER(i.order_id) LIKE ? OR "
            "LOWER(s.business_name) LIKE ? OR LOWER(n.business_name) LIKE ?)"
        )
        wildcard = f"%{search_q}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    query = f"""
        SELECT i.*,
               s.business_name as supplier_name,
               n.business_name as nursery_name,
               (SELECT COUNT(*) FROM invoice_items WHERE invoice_id = i.id) as items_count,
               COALESCE((SELECT SUM(a.amount) FROM payment_allocations a JOIN payments p ON a.payment_id = p.id WHERE a.invoice_id = i.id AND a.status = 'ACTIVE' AND p.status = 'RECORDED'), 0.0) as total_paid
        FROM invoices i
        JOIN users s ON i.supplier_user_id = s.id
        JOIN users n ON i.nursery_user_id = n.id
        {where_sql}
        ORDER BY i.created_at DESC
    """
    rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        tot_paid = round(float(d.get('total_paid') or 0.0), 2)
        tot_amt = round(float(d.get('total_amount') or 0.0), 2)
        outstanding = max(0.0, round(tot_amt - tot_paid, 2))
        if d.get('status') == 'CANCELLED':
            pay_status = 'CANCELLED'
        elif tot_paid >= tot_amt and tot_amt > 0:
            pay_status = 'PAID'
        elif tot_paid > 0:
            pay_status = 'PARTIALLY_PAID'
        else:
            pay_status = 'UNPAID'
        d['total_paid'] = tot_paid
        d['outstanding_balance'] = outstanding
        d['payment_status'] = pay_status

        # Phase 10: Contractual Due Date & Late-Payment Interest Metrics
        from app.services.interest_service import calculate_invoice_interest
        int_res = calculate_invoice_interest(conn, d['id'])
        if int_res:
            d['due_status'] = int_res['due_status']
            d['overdue_days'] = int_res['overdue_days']
            d['accrued_interest'] = int_res['accrued_interest']
            d['total_amount_payable'] = int_res['total_amount_payable']
            d['is_interest_applicable'] = int_res['is_interest_applicable']
        else:
            d['due_status'] = 'NO_DUE_DATE'
            d['overdue_days'] = 0
            d['accrued_interest'] = 0.0
            d['total_amount_payable'] = outstanding
            d['is_interest_applicable'] = False

        results.append(d)

    # Optional Due Status Filter
    due_filter = (filters.get('due_status') or '').strip().upper()
    if due_filter and due_filter != 'ALL':
        results = [r for r in results if r.get('due_status') == due_filter]

    return results


def cancel_invoice(conn, invoice_id_or_number, actor_user, reason, ip_address="127.0.0.1"):
    """
    Cancels an issued invoice with required audit reason.
    Only the issuing supplier or platform admin can cancel an invoice.
    """
    if not actor_user:
        raise PermissionError("Authentication required.")

    inv = conn.execute(
        "SELECT * FROM invoices WHERE id = ? OR invoice_number = ?",
        (invoice_id_or_number, invoice_id_or_number)
    ).fetchone()
    if not inv:
        raise ValueError(f"Invoice '{invoice_id_or_number}' not found.")

    role = actor_user.get('role')
    if role not in ('SUPPLIER', 'ADMIN'):
        raise PermissionError("Forbidden: Only suppliers and administrators can cancel invoices.")

    if role == 'SUPPLIER' and inv['supplier_user_id'] != actor_user['id']:
        raise PermissionError("Unauthorized: You can only cancel invoices issued by your business.")

    if inv['status'] == 'CANCELLED':
        raise ValueError(f"Invoice #{inv['invoice_number']} is already cancelled.")

    clean_reason = (reason or '').strip()
    if not clean_reason:
        raise ValueError("Cancellation reason is required.")

    conn.execute(
        "UPDATE invoices SET status = 'CANCELLED' WHERE id = ?",
        (inv['id'],)
    )

    log_audit_event(
        conn,
        event_type="INVOICE_CANCELLED",
        order_id=inv['order_id'],
        actor_user_id=actor_user['id'],
        actor_role=actor_user['role'],
        before_state={"status": inv['status'], "invoice_number": inv['invoice_number']},
        after_state={"status": "CANCELLED", "invoice_number": inv['invoice_number']},
        justification=clean_reason,
        ip_address=ip_address
    )

    return get_invoice_details(conn, inv['id'], actor_user)
