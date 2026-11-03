"""
FloraChain B2B — Truck Loading & Transport Manifest Service
Phase 7: Wholesale Order Vehicle Staging, Item Loading Progress & Dispatch Engine

Enforces:
- Retrieval of eligible order plant varieties and quantities for truck loading
- Itemized tracking of loaded quantities: 0 <= loaded_qty <= ordered_qty
- Strict server-side mathematical validation preventing negative or excessive quantities
- Automatic calculation of loaded units, remaining units, and completion percentages
- Persistence of vehicle number (truck_no) and driver details (driver_info)
- Server-side role authorization and supplier ownership enforcement
- Immutability enforcement on finalized and locked orders
- Append-only audit trail logging for truck staging and dispatch events
"""

import json
from app.services.audit_service import log_audit_event


def calculate_loading_summary(items):
    """
    Computes aggregate truck loading metrics across an order's line items.
    """
    total_ordered = sum(it['quantity'] for it in items)
    total_loaded = sum(it.get('loaded_qty', 0) for it in items)
    total_remaining = max(0, total_ordered - total_loaded)
    is_fully_loaded = (total_loaded == total_ordered) and total_ordered > 0
    loading_pct = round((total_loaded / total_ordered) * 100.0, 1) if total_ordered > 0 else 0.0

    return {
        "total_ordered_qty": total_ordered,
        "total_loaded_qty": total_loaded,
        "total_remaining_qty": total_remaining,
        "is_fully_loaded": is_fully_loaded,
        "loading_pct": loading_pct
    }


def get_truck_loading_details(conn, order_id, actor_user=None):
    """
    Retrieves complete truck loading manifest details for an order.
    Includes ordered varieties, quantities loaded, remaining counts, vehicle, driver, and lock state.
    """
    order = conn.execute(
        """SELECT o.*, 
                  s.username as supplier_username, s.business_name as supplier_name,
                  n.username as nursery_username, n.business_name as nursery_name,
                  di.is_locked as inspection_is_locked, di.status as inspection_status
           FROM orders o
           JOIN users s ON o.supplier_user_id = s.id
           JOIN users n ON o.nursery_user_id = n.id
           LEFT JOIN delivery_inspections di ON o.id = di.order_id
           WHERE o.id = ?""",
        (order_id,)
    ).fetchone()

    if not order:
        return None

    order_dict = dict(order)

    # Role authorization & ownership check
    if actor_user and actor_user.get('role') != 'ADMIN':
        user_id = actor_user.get('id')
        if user_id not in (order_dict['supplier_user_id'], order_dict['nursery_user_id']):
            raise PermissionError(f"Unauthorized: You do not have access to Order #{order_id} loading manifest.")

    # Fetch Itemized Lines
    items_rows = conn.execute(
        """SELECT oi.*, p.category, p.container_size, p.unit
           FROM order_items oi
           LEFT JOIN plants p ON oi.plant_id = p.id
           WHERE oi.order_id = ?
           ORDER BY oi.id ASC""",
        (order_id,)
    ).fetchall()

    items = []
    for r in items_rows:
        it = dict(r)
        qty = it['quantity']
        loaded = it.get('loaded_qty', 0)
        remaining = max(0, qty - loaded)
        it['remaining_qty'] = remaining
        it['is_fully_loaded'] = (loaded == qty)
        it['loading_pct'] = round((loaded / qty) * 100.0, 1) if qty > 0 else 0.0
        items.append(it)

    summary = calculate_loading_summary(items)

    # Immutability & Editability rules
    is_locked = bool(order_dict.get('inspection_is_locked')) or order_dict['status'] in ('LOCKED_VERIFIED', 'DELIVERED', 'CANCELLED')
    is_editable = (not is_locked) and (actor_user is None or actor_user.get('role') in ('SUPPLIER', 'ADMIN'))
    lock_reason = ""
    if is_locked:
        lock_reason = f"Order #{order_id} is {order_dict['status']} and finalized. Manifest cannot be edited."
    elif actor_user and actor_user.get('role') == 'NURSERY':
        lock_reason = "Receiving nurseries have read-only visibility into supplier truck loading manifests."

    return {
        "order": order_dict,
        "items": items,
        "items_count": len(items),
        "total_ordered_qty": summary["total_ordered_qty"],
        "total_loaded_qty": summary["total_loaded_qty"],
        "total_remaining_qty": summary["total_remaining_qty"],
        "is_fully_loaded": summary["is_fully_loaded"],
        "loading_pct": summary["loading_pct"],
        "is_editable": is_editable,
        "lock_reason": lock_reason
    }


def save_truck_loading(conn, order_id, actor_user, data, ip_address="127.0.0.1"):
    """
    Saves loading quantities, vehicle registration, and driver details.
    Enforces:
    - User authentication and Supplier role ownership
    - Immutability of locked/verified orders
    - Server-side mathematical validation: 0 <= loaded_qty <= ordered_qty
    - Optional vehicle dispatch state transition (status -> 'DISPATCHED')
    - Audit event logging into audit_events
    """
    if not actor_user:
        raise PermissionError("Authentication required.")

    role = actor_user.get('role')
    if role not in ('SUPPLIER', 'ADMIN'):
        raise PermissionError("Only wholesale suppliers and platform administrators can record truck loading.")

    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        raise ValueError(f"Order #{order_id} not found.")

    order_dict = dict(order)

    # Ownership check
    if role == 'SUPPLIER' and order_dict['supplier_user_id'] != actor_user['id']:
        raise PermissionError(f"Unauthorized: You are not the assigned wholesale supplier for Order #{order_id}.")

    # Immutability check
    if order_dict['status'] in ('LOCKED_VERIFIED', 'DELIVERED', 'CANCELLED'):
        raise PermissionError(f"Order #{order_id} is {order_dict['status']} and finalized. Loading cannot be modified.")

    inspection = conn.execute("SELECT is_locked FROM delivery_inspections WHERE order_id = ?", (order_id,)).fetchone()
    if inspection and inspection['is_locked'] == 1:
        raise PermissionError(f"Order #{order_id} has been delivery-verified and locked. Truck loading is immutable.")

    # Fetch existing items
    items_rows = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    items_by_id = {it['id']: dict(it) for it in items_rows}

    # Process incoming loaded quantities
    items_payload = data.get('items', [])
    updated_items = []

    # Map payload items by item ID or plant_id
    payload_map = {}
    for entry in items_payload:
        if isinstance(entry, dict):
            if 'id' in entry and entry['id'] is not None:
                payload_map[entry['id']] = entry
            elif 'plant_id' in entry and entry['plant_id'] is not None:
                # Find matching item by plant_id
                for item_id, it in items_by_id.items():
                    if it['plant_id'] == entry['plant_id']:
                        payload_map[item_id] = entry
                        break

    for item_id, item in items_by_id.items():
        ordered_qty = item['quantity']
        variety = item['variety']

        if item_id in payload_map:
            raw_loaded = payload_map[item_id].get('loaded_qty')
            if raw_loaded is None:
                raw_loaded = item.get('loaded_qty', 0)

            try:
                # Explicit integer check (reject bool, floats)
                if type(raw_loaded) is bool or not isinstance(raw_loaded, (int, float)):
                    raise ValueError()
                loaded_qty = int(raw_loaded)
            except (ValueError, TypeError):
                raise ValueError(f"Loaded quantity for '{variety}' must be a whole non-negative integer.")

            if loaded_qty < 0:
                raise ValueError(f"Loaded quantity for '{variety}' cannot be negative ({loaded_qty}).")

            if loaded_qty > ordered_qty:
                raise ValueError(
                    f"Loaded quantity ({loaded_qty}) cannot exceed ordered quantity ({ordered_qty}) for '{variety}'."
                )
        else:
            loaded_qty = item.get('loaded_qty', 0)

        updated_items.append({
            "id": item_id,
            "variety": variety,
            "quantity": ordered_qty,
            "loaded_qty": loaded_qty
        })

    summary = calculate_loading_summary(updated_items)

    # Transport vehicle details
    truck_no = (data.get('truck_no') or order_dict['truck_no'] or 'TBD').strip()
    driver_info = (data.get('driver_info') or order_dict['driver_info'] or 'TBD').strip()
    notes = (data.get('notes') or data.get('loading_notes') or order_dict.get('loading_notes') or '').strip()
    is_dispatch = bool(data.get('dispatch', False))

    # Dispatch validation
    if is_dispatch:
        if not truck_no or truck_no.upper() == 'TBD':
            raise ValueError("A valid transport vehicle/truck number is required to dispatch.")
        if not driver_info or driver_info.upper() == 'TBD':
            raise ValueError("Driver name and contact information are required to dispatch.")
        if summary["total_loaded_qty"] <= 0:
            raise ValueError("Cannot dispatch transport vehicle with 0 loaded plant units.")

        new_status = 'DISPATCHED'
    else:
        # Saving staging progress
        if summary["total_loaded_qty"] > 0 and order_dict['status'] == 'CONFIRMED':
            new_status = 'STAGING'
        else:
            new_status = order_dict['status']

    # Update order items loaded_qty
    for it in updated_items:
        conn.execute(
            "UPDATE order_items SET loaded_qty = ? WHERE id = ?",
            (it['loaded_qty'], it['id'])
        )

    # Update order transport and status
    if is_dispatch:
        conn.execute(
            """UPDATE orders 
               SET truck_no = ?, driver_info = ?, status = ?, loading_notes = ?, loaded_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (truck_no, driver_info, new_status, notes, order_id)
        )
    else:
        conn.execute(
            """UPDATE orders 
               SET truck_no = ?, driver_info = ?, status = ?, loading_notes = ?
               WHERE id = ?""",
            (truck_no, driver_info, new_status, notes, order_id)
        )

    # Audit Trail Logging
    before_state = {
        "status": order_dict['status'],
        "truck_no": order_dict['truck_no'],
        "driver_info": order_dict['driver_info'],
        "total_loaded_qty": sum(it.get('loaded_qty', 0) for it in items_by_id.values())
    }
    after_state = {
        "status": new_status,
        "truck_no": truck_no,
        "driver_info": driver_info,
        "total_loaded_qty": summary["total_loaded_qty"],
        "total_ordered_qty": summary["total_ordered_qty"],
        "is_fully_loaded": summary["is_fully_loaded"],
        "loading_notes": notes
    }

    event_type = "TRUCK_DISPATCHED" if is_dispatch else "TRUCK_LOADING_UPDATED"
    justification = notes or ("Truck dispatched with full batch." if is_dispatch else "Truck loading staging progress updated.")

    log_audit_event(
        conn,
        event_type=event_type,
        order_id=order_id,
        actor_user_id=actor_user['id'],
        actor_role=actor_user['role'],
        before_state=before_state,
        after_state=after_state,
        justification=justification,
        ip_address=ip_address
    )

    return get_truck_loading_details(conn, order_id, actor_user)


def list_truck_manifests(conn, actor_user, filters=None):
    """
    Returns platform orders for the Truck Loading Manifest Board.
    Enforces role isolation (Suppliers see their trucks, Nurseries see their incoming trucks, Admins see all).
    Supports status and search filtering.
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

    # Status Filter
    status_filter = (filters.get('status') or '').strip().upper()
    if status_filter and status_filter != 'ALL':
        if status_filter == 'STAGING':
            where_clauses.append("o.status IN ('CONFIRMED', 'STAGING')")
        elif status_filter == 'COMPLETED':
            where_clauses.append("o.status IN ('DELIVERED', 'LOCKED_VERIFIED')")
        else:
            where_clauses.append("o.status = ?")
            params.append(status_filter)

    # Search query
    search_q = (filters.get('search') or filters.get('q') or '').strip().lower()
    if search_q:
        where_clauses.append(
            "(LOWER(o.id) LIKE ? OR LOWER(o.truck_no) LIKE ? OR LOWER(o.driver_info) LIKE ? OR LOWER(n.business_name) LIKE ? OR LOWER(o.variety) LIKE ?)"
        )
        wildcard = f"%{search_q}%"
        params.extend([wildcard, wildcard, wildcard, wildcard, wildcard])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    query = f"""
        SELECT o.id as order_id, o.variety, o.ordered_qty, o.truck_no, o.driver_info,
               o.status, o.loaded_at, o.loading_notes, o.created_at,
               s.business_name as supplier_name, s.username as supplier_username,
               n.business_name as nursery_name, n.username as nursery_username,
               COALESCE((SELECT SUM(loaded_qty) FROM order_items WHERE order_id = o.id), 0) as total_loaded_qty,
               (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as items_count
        FROM orders o
        JOIN users s ON o.supplier_user_id = s.id
        JOIN users n ON o.nursery_user_id = n.id
        {where_sql}
        ORDER BY o.created_at DESC
    """
    rows = conn.execute(query, params).fetchall()

    manifests = []
    for r in rows:
        m = dict(r)
        ordered = m['ordered_qty']
        loaded = m['total_loaded_qty']
        remaining = max(0, ordered - loaded)
        is_fully_loaded = (loaded == ordered) and ordered > 0
        loading_pct = round((loaded / ordered) * 100.0, 1) if ordered > 0 else 0.0

        m['remaining_qty'] = remaining
        m['is_fully_loaded'] = is_fully_loaded
        m['loading_pct'] = loading_pct
        manifests.append(m)

    return manifests

