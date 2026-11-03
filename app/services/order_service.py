"""
FloraChain B2B — Wholesale Order Management Service
Phase 6: Multi-Variety Order Management, Itemized Lines & Platform Order Lifecycle

Enforces:
- Order creation linking supplier, client nursery, and selected plant varieties
- Multi-item line calculation: line_total = quantity * unit_price
- Order totals: total_ordered_qty, weighted average unit_price, grand total amount
- Server-side validation of positive integer quantities, valid prices, and active plant catalog items
- Role-based authorization & data isolation (Supplier vs Nursery vs Admin)
- Append-only audit trail logging for all order creation events
- Backward compatibility with physical delivery verification (Phase 3) & deal agreements (Phase 4/Stage 4)
"""

import json
from app.services.audit_service import log_audit_event


def validate_order_item(conn, item_data, index=0):
    """
    Validates an individual order line item:
    - quantity must be a positive integer
    - unit_price must be a positive number
    - plant_id (if supplied) must exist in plants catalog
    - variety name must not be empty
    """
    if not isinstance(item_data, dict):
        raise ValueError(f"Item #{index + 1}: Invalid item structure.")

    # 1. Quantity validation
    qty_val = item_data.get('quantity')
    if type(qty_val) is not int or qty_val <= 0:
        raise ValueError(f"Item #{index + 1}: Quantity must be a positive whole integer greater than zero.")

    # 2. Plant lookup if plant_id provided
    plant_id = item_data.get('plant_id')
    plant_row = None
    if plant_id:
        try:
            plant_id = int(plant_id)
        except (ValueError, TypeError):
            raise ValueError(f"Item #{index + 1}: Invalid plant ID '{plant_id}'.")

        plant_row = conn.execute("SELECT * FROM plants WHERE id = ?", (plant_id,)).fetchone()
        if not plant_row:
            raise ValueError(f"Item #{index + 1}: Plant ID #{plant_id} does not exist in catalog.")

        if plant_row['status'] == 'DISCONTINUED':
            raise ValueError(f"Item #{index + 1}: Plant '{plant_row['common_name']}' is discontinued and cannot be ordered.")

        if qty_val < plant_row['min_order_qty']:
            raise ValueError(
                f"Item #{index + 1}: Quantity ({qty_val}) is below minimum order quantity ({plant_row['min_order_qty']}) "
                f"for '{plant_row['common_name']}'."
            )

    # 3. Variety name
    variety = (item_data.get('variety') or (plant_row['common_name'] if plant_row else '')).strip()
    if not variety:
        raise ValueError(f"Item #{index + 1}: Variety name is required.")

    # 4. Unit price validation
    price_val = item_data.get('unit_price')
    if price_val is None and plant_row:
        price_val = float(plant_row['unit_price'])
    else:
        try:
            price_val = float(price_val)
        except (ValueError, TypeError):
            raise ValueError(f"Item #{index + 1}: Unit price must be a valid number.")

    if price_val <= 0:
        raise ValueError(f"Item #{index + 1}: Unit price must be greater than zero.")

    line_total = round(qty_val * price_val, 2)

    return {
        "plant_id": plant_id,
        "variety": variety,
        "quantity": qty_val,
        "unit_price": round(price_val, 2),
        "line_total": line_total
    }


def generate_next_order_id(conn):
    """
    Generates a human-friendly unique order ID (e.g. ORD-9101).
    """
    rows = conn.execute("SELECT id FROM orders WHERE id LIKE 'ORD-%'").fetchall()
    highest = 9100
    for r in rows:
        val = r['id'].replace('ORD-', '')
        if val.isdigit():
            num = int(val)
            if num > highest:
                highest = num
    return f"ORD-{highest + 1}"


def create_order(conn, actor_user, data, ip_address="127.0.0.1"):
    """
    Creates a new wholesale plant order with itemized lines.
    Enforces:
    - Authentication and authorization (Suppliers and Admins can create orders)
    - Valid nursery recipient
    - At least one valid plant item
    - Correct calculation of line totals, grand total, and weighted unit price
    - Audit event logging
    """
    if not actor_user:
        raise PermissionError("Authentication required.")

    role = actor_user.get('role')
    if role not in ('SUPPLIER', 'ADMIN'):
        raise PermissionError("Only wholesale suppliers and platform administrators can create wholesale orders.")

    # 1. Determine supplier ID
    if role == 'SUPPLIER':
        supplier_user_id = actor_user['id']
    else:
        supplier_user_id = data.get('supplier_user_id')
        if not supplier_user_id:
            first_supp = conn.execute("SELECT id FROM users WHERE role = 'SUPPLIER' ORDER BY id ASC LIMIT 1").fetchone()
            if not first_supp:
                raise ValueError("No supplier account found on platform.")
            supplier_user_id = first_supp['id']
        else:
            supp_check = conn.execute("SELECT id FROM users WHERE id = ? AND role = 'SUPPLIER'", (supplier_user_id,)).fetchone()
            if not supp_check:
                raise ValueError(f"User #{supplier_user_id} is not an active wholesale supplier.")

    # 2. Validate nursery recipient
    nursery_user_id = data.get('nursery_user_id')
    if not nursery_user_id:
        raise ValueError("Client nursery partner (nursery_user_id) is required.")

    try:
        nursery_user_id = int(nursery_user_id)
    except (ValueError, TypeError):
        raise ValueError("Invalid nursery_user_id format.")

    nursery_row = conn.execute("SELECT * FROM users WHERE id = ? AND role = 'NURSERY'", (nursery_user_id,)).fetchone()
    if not nursery_row:
        raise ValueError(f"Nursery ID #{nursery_user_id} does not exist or is not a registered nursery partner.")

    # 3. Validate items array
    items_raw = data.get('items')
    if not items_raw or not isinstance(items_raw, list) or len(items_raw) == 0:
        raise ValueError("At least one plant line item is required to create an order.")

    sanitized_items = []
    for idx, raw_item in enumerate(items_raw):
        clean_item = validate_order_item(conn, raw_item, index=idx)
        sanitized_items.append(clean_item)

    # 4. Compute totals and summary variety
    total_qty = sum(item['quantity'] for item in sanitized_items)
    grand_total = round(sum(item['line_total'] for item in sanitized_items), 2)
    avg_unit_price = round(grand_total / total_qty, 2) if total_qty > 0 else 0.0

    if len(sanitized_items) == 1:
        variety_summary = sanitized_items[0]['variety']
    else:
        variety_summary = f"{sanitized_items[0]['variety']} (+{len(sanitized_items) - 1} more varieties)"

    # 5. Order metadata
    order_id = (data.get('id') or '').strip()
    if not order_id:
        order_id = generate_next_order_id(conn)
    else:
        existing = conn.execute("SELECT id FROM orders WHERE id = ?", (order_id,)).fetchone()
        if existing:
            raise ValueError(f"Order #{order_id} already exists.")

    truck_no = (data.get('truck_no') or 'TBD').strip()
    driver_info = (data.get('driver_info') or 'TBD').strip()
    status = (data.get('status') or 'CONFIRMED').strip()
    valid_statuses = ('DRAFT', 'CONFIRMED', 'STAGING', 'DISPATCHED', 'INSPECTED_PENDING_CONFIRMATION', 'DELIVERED', 'LOCKED_VERIFIED', 'CANCELLED')
    if status not in valid_statuses:
        raise ValueError(f"Invalid order status '{status}'. Must be one of: {', '.join(valid_statuses)}")

    # 6. Insert Order Header
    conn.execute(
        """INSERT INTO orders
           (id, supplier_user_id, nursery_user_id, variety, ordered_qty, unit_price, truck_no, driver_info, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (order_id, supplier_user_id, nursery_user_id, variety_summary, total_qty, avg_unit_price, truck_no, driver_info, status)
    )

    # 7. Insert Order Line Items
    for item in sanitized_items:
        conn.execute(
            """INSERT INTO order_items
               (order_id, plant_id, variety, quantity, unit_price, line_total)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (order_id, item['plant_id'], item['variety'], item['quantity'], item['unit_price'], item['line_total'])
        )

    # 8. Log Audit Event
    after_state = {
        "id": order_id,
        "supplier_user_id": supplier_user_id,
        "nursery_user_id": nursery_user_id,
        "variety_summary": variety_summary,
        "total_qty": total_qty,
        "grand_total": grand_total,
        "status": status,
        "items_count": len(sanitized_items)
    }
    log_audit_event(
        conn,
        event_type="ORDER_CREATED",
        order_id=order_id,
        actor_user_id=actor_user['id'],
        actor_role=actor_user['role'],
        before_state=None,
        after_state=after_state,
        justification=data.get('notes', '').strip() or f"New wholesale order created with {len(sanitized_items)} plant lines.",
        ip_address=ip_address
    )

    return get_order_details(conn, order_id, actor_user)


def list_orders_for_user(conn, actor_user, filters=None):
    """
    Returns platform wholesale orders accessible to the authenticated user.
    Enforces role isolation:
    - SUPPLIER: sees orders where supplier_user_id = user['id']
    - NURSERY: sees orders where nursery_user_id = user['id']
    - ADMIN: sees all platform orders
    """
    filters = filters or {}
    params = []
    where_clauses = []

    # Role Isolation
    if actor_user['role'] == 'SUPPLIER':
        where_clauses.append("o.supplier_user_id = ?")
        params.append(actor_user['id'])
    elif actor_user['role'] == 'NURSERY':
        where_clauses.append("o.nursery_user_id = ?")
        params.append(actor_user['id'])
    # ADMIN has full visibility across all orders

    # Status Filter
    status_filter = (filters.get('status') or '').strip()
    if status_filter and status_filter.upper() != 'ALL':
        where_clauses.append("o.status = ?")
        params.append(status_filter.upper())

    # Search Query
    search_q = (filters.get('search') or filters.get('q') or '').strip().lower()
    if search_q:
        where_clauses.append("(LOWER(o.id) LIKE ? OR LOWER(o.variety) LIKE ? OR LOWER(s.business_name) LIKE ? OR LOWER(n.business_name) LIKE ?)")
        wildcard = f"%{search_q}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    query = f"""
        SELECT o.*,
               s.username as supplier_username, s.business_name as supplier_name,
               n.username as nursery_username, n.business_name as nursery_name,
               di.id as inspection_id, di.delivered_qty, di.sound_qty, di.damaged_qty,
               di.damage_pct, di.damage_notes, di.is_locked, di.status as inspection_status,
               di.locked_at,
               (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as items_count,
               COALESCE((SELECT SUM(line_total) FROM order_items WHERE order_id = o.id), ROUND(o.ordered_qty * o.unit_price, 2)) as total_amount
        FROM orders o
        JOIN users s ON o.supplier_user_id = s.id
        JOIN users n ON o.nursery_user_id = n.id
        LEFT JOIN delivery_inspections di ON o.id = di.order_id
        {where_sql}
        ORDER BY o.created_at DESC
    """
    rows = conn.execute(query, params).fetchall()
    orders = []
    for r in rows:
        item_dict = dict(r)
        # Ensure is_locked is a boolean if present
        if item_dict.get('is_locked') is not None:
            item_dict['is_locked'] = bool(item_dict['is_locked'])
        orders.append(item_dict)
    return orders


def get_order_details(conn, order_id, actor_user=None):
    """
    Retrieves full details of a wholesale order:
    - Order header with supplier & nursery profiles
    - Itemized order_items lines with plant catalog specs
    - Physical arrival inspection metrics & dual counter-signatures
    - Linked deal agreement details
    """
    order = conn.execute(
        """SELECT o.*,
                  s.username as supplier_username, s.business_name as supplier_name,
                  n.username as nursery_username, n.business_name as nursery_name
           FROM orders o
           JOIN users s ON o.supplier_user_id = s.id
           JOIN users n ON o.nursery_user_id = n.id
           WHERE o.id = ?""",
        (order_id,)
    ).fetchone()

    if not order:
        return None

    order_dict = dict(order)

    # Permission check if actor_user provided
    if actor_user and actor_user['role'] != 'ADMIN':
        if actor_user['id'] not in (order['supplier_user_id'], order['nursery_user_id']):
            raise PermissionError(f"Unauthorized: You do not have permission to view Order #{order_id}.")

    # Fetch Itemized Lines
    items_rows = conn.execute(
        """SELECT oi.*, p.category, p.container_size, p.unit
           FROM order_items oi
           LEFT JOIN plants p ON oi.plant_id = p.id
           WHERE oi.order_id = ?
           ORDER BY oi.id ASC""",
        (order_id,)
    ).fetchall()
    items = [dict(it) for it in items_rows]

    # Calculate total order value
    if items:
        total_amount = round(sum(it['line_total'] for it in items), 2)
        total_qty = sum(it['quantity'] for it in items)
    else:
        total_amount = round(order_dict['ordered_qty'] * order_dict['unit_price'], 2)
        total_qty = order_dict['ordered_qty']

    order_dict['items_count'] = len(items)
    order_dict['total_amount'] = total_amount

    # Physical Delivery Inspection Details
    inspection = conn.execute("SELECT * FROM delivery_inspections WHERE order_id = ?", (order_id,)).fetchone()
    confirmations = []
    if inspection:
        conf_rows = conn.execute(
            """SELECT c.*, u.username, u.business_name
               FROM inspection_confirmations c
               JOIN users u ON c.user_id = u.id
               WHERE c.inspection_id = ?
               ORDER BY c.confirmed_at ASC""",
            (inspection["id"],)
        ).fetchall()
        for c in conf_rows:
            confirmations.append({
                "party_role": c["party_role"],
                "confirmed_at": c["confirmed_at"],
                "user_id": c["user_id"],
                "user_name": c["username"],
                "business_name": c["business_name"],
                "signature_note": c["signature_note"]
            })

    confirmed_roles = {c["party_role"] for c in confirmations}

    # Linked Deal Agreement
    agreement = conn.execute(
        "SELECT id, agreement_ref, status, total_order_value, advance_amount, balance_amount, payment_due_date FROM deal_agreements WHERE order_id = ? ORDER BY version DESC LIMIT 1",
        (order_id,)
    ).fetchone()

    return {
        "order": order_dict,
        "items": items,
        "items_count": len(items),
        "total_amount": total_amount,
        "total_qty": total_qty,
        "inspection": dict(inspection) if inspection else None,
        "confirmations": confirmations,
        "nursery_confirmed": "NURSERY" in confirmed_roles,
        "supplier_confirmed": "SUPPLIER" in confirmed_roles,
        "is_locked": bool(inspection["is_locked"]) if inspection else False,
        "status": inspection["status"] if inspection else order_dict["status"],
        "agreement": dict(agreement) if agreement else None
    }


def list_nurseries_for_orders(conn):
    """
    Returns list of registered nursery partners for order creation forms.
    """
    rows = conn.execute(
        "SELECT id, username, business_name, email FROM users WHERE role = 'NURSERY' ORDER BY business_name ASC"
    ).fetchall()
    return [dict(r) for r in rows]

