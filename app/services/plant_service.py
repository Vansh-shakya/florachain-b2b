"""
FloraChain B2B — Plant Catalog & Inventory Service
Phase 5: Plant Management Backend Service Engine

Enforces:
- Input validation and schema constraints for wholesale plant catalog
- Supplier-scoped inventory ownership & modification safeguards
- Access isolation preventing cross-supplier private inventory tampering
- Parametrized SQL execution and transactional integrity
"""

import json
from datetime import datetime

VALID_CATEGORIES = (
    'INDOOR', 'OUTDOOR', 'FLOWERING', 'ORNAMENTAL',
    'TREE', 'PALM', 'SUCCULENT', 'CLIMBER',
    'SEASONAL', 'MEDICINAL', 'FRUIT', 'OTHER'
)

VALID_UNITS = ('plant', 'tray', 'bag', 'pot', 'bundle')

VALID_STATUSES = ('ACTIVE', 'DISCONTINUED', 'OUT_OF_STOCK')


def validate_plant_data(data, is_update=False, existing=None):
    """
    Validates plant catalog attributes and schema constraints.
    Returns a sanitized dictionary of fields, or raises ValueError.
    """
    if not isinstance(data, dict):
        raise ValueError("Invalid payload: expected JSON object.")

    existing = existing or {}
    validated = {}

    # 1. Common Name (Required on create, optional on update)
    if 'common_name' in data or not is_update:
        common_name = data.get('common_name')
        if common_name is None or not str(common_name).strip():
            raise ValueError("Plant common name is required and cannot be empty.")
        validated['common_name'] = str(common_name).strip()
    else:
        validated['common_name'] = existing.get('common_name')

    # 2. Botanical Name (Optional)
    if 'botanical_name' in data:
        botanical_name = data.get('botanical_name')
        validated['botanical_name'] = str(botanical_name).strip() if botanical_name is not None else ''
    elif not is_update:
        validated['botanical_name'] = ''
    else:
        validated['botanical_name'] = existing.get('botanical_name', '')

    # 3. Category (Required on create, optional on update)
    if 'category' in data or not is_update:
        category_raw = data.get('category')
        if not category_raw or not str(category_raw).strip():
            raise ValueError(f"Plant category is required. Must be one of: {', '.join(VALID_CATEGORIES)}")
        category = str(category_raw).strip().upper()
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{category_raw}'. Must be one of: {', '.join(VALID_CATEGORIES)}")
        validated['category'] = category
    else:
        validated['category'] = existing.get('category')

    # 4. Container Size (Required on create, optional on update)
    if 'container_size' in data or not is_update:
        container_size = data.get('container_size')
        if container_size is None or not str(container_size).strip():
            raise ValueError("Container size is required (e.g. '12-inch Pot', '8-inch Heavy Bag').")
        validated['container_size'] = str(container_size).strip()
    else:
        validated['container_size'] = existing.get('container_size')

    # 5. Unit (Optional, defaults to 'plant')
    if 'unit' in data:
        unit_raw = data.get('unit')
        if not unit_raw or not str(unit_raw).strip():
            raise ValueError(f"Invalid unit. Must be one of: {', '.join(VALID_UNITS)}")
        unit = str(unit_raw).strip().lower()
        if unit not in VALID_UNITS:
            raise ValueError(f"Invalid unit '{unit_raw}'. Must be one of: {', '.join(VALID_UNITS)}")
        validated['unit'] = unit
    elif not is_update:
        validated['unit'] = 'plant'
    else:
        validated['unit'] = existing.get('unit', 'plant')

    # 6. Unit Price (Required on create, optional on update)
    if 'unit_price' in data or not is_update:
        price_raw = data.get('unit_price')
        if isinstance(price_raw, bool) or price_raw is None:
            raise ValueError("Unit price must be a valid positive number.")
        try:
            price = float(price_raw)
            if price <= 0:
                raise ValueError()
            validated['unit_price'] = round(price, 2)
        except (TypeError, ValueError):
            raise ValueError("Unit price must be a positive number greater than zero.")
    else:
        validated['unit_price'] = existing.get('unit_price')

    # 7. Stock Quantity (Optional, defaults to 0)
    if 'stock_qty' in data:
        stock_raw = data.get('stock_qty')
        if isinstance(stock_raw, bool) or stock_raw is None:
            raise ValueError("Stock quantity must be a non-negative whole integer.")
        try:
            stock = int(stock_raw)
            if stock < 0 or float(stock_raw) != stock:
                raise ValueError()
            validated['stock_qty'] = stock
        except (TypeError, ValueError):
            raise ValueError("Stock quantity must be a non-negative whole integer.")
    elif not is_update:
        validated['stock_qty'] = 0
    else:
        validated['stock_qty'] = existing.get('stock_qty', 0)

    # 8. Minimum Order Quantity (Optional, defaults to 1)
    if 'min_order_qty' in data:
        min_raw = data.get('min_order_qty')
        if isinstance(min_raw, bool) or min_raw is None:
            raise ValueError("Minimum order quantity must be an integer of 1 or greater.")
        try:
            min_qty = int(min_raw)
            if min_qty < 1 or float(min_raw) != min_qty:
                raise ValueError()
            validated['min_order_qty'] = min_qty
        except (TypeError, ValueError):
            raise ValueError("Minimum order quantity must be an integer of 1 or greater.")
    elif not is_update:
        validated['min_order_qty'] = 1
    else:
        validated['min_order_qty'] = existing.get('min_order_qty', 1)

    # 9. Description (Optional)
    if 'description' in data:
        desc = data.get('description')
        validated['description'] = str(desc).strip() if desc is not None else ''
    elif not is_update:
        validated['description'] = ''
    else:
        validated['description'] = existing.get('description', '')

    # 10. Status (Optional, defaults to 'ACTIVE')
    if 'status' in data:
        status_raw = data.get('status')
        if not status_raw or not str(status_raw).strip():
            raise ValueError(f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")
        status = str(status_raw).strip().upper()
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status_raw}'. Must be one of: {', '.join(VALID_STATUSES)}")
        validated['status'] = status
    elif not is_update:
        validated['status'] = 'ACTIVE'
    else:
        validated['status'] = existing.get('status', 'ACTIVE')

    return validated


def list_plants(conn, user, filters=None):
    """
    Returns plant catalog records with optional search, category, and status filtering.
    
    Access Control & Privacy Rules:
    - SUPPLIER:
        - When scope='mine' or supplier_id=user['id'], lists their own catalog (including DISCONTINUED).
        - When viewing general catalog or other suppliers, DISCONTINUED items of other suppliers are excluded.
    - NURSERY:
        - Views active wholesale catalog across suppliers. DISCONTINUED items are never displayed.
    - ADMIN:
        - Has platform-wide compliance audit visibility.
    """
    filters = filters or {}
    conditions = []
    params = []

    # Supplier isolation & status visibility
    if user and user.get('role') == 'SUPPLIER':
        supplier_id_filter = filters.get('supplier_id')
        scope = (filters.get('scope') or '').lower().strip()

        if scope == 'mine' or (supplier_id_filter and str(supplier_id_filter) == str(user['id'])):
            # Direct view of own inventory
            conditions.append("p.supplier_user_id = ?")
            params.append(user['id'])
        elif supplier_id_filter:
            # Viewing a specific other supplier's offerings
            conditions.append("p.supplier_user_id = ?")
            params.append(int(supplier_id_filter))
            # Hide other supplier's discontinued inventory
            conditions.append("p.status != 'DISCONTINUED'")
        else:
            # General browsing: show all, but exclude other suppliers' discontinued records
            conditions.append("(p.supplier_user_id = ? OR p.status != 'DISCONTINUED')")
            params.append(user['id'])
    elif user and user.get('role') == 'NURSERY':
        # Nurseries never see discontinued stock
        conditions.append("p.status != 'DISCONTINUED'")
        if filters.get('supplier_id'):
            conditions.append("p.supplier_user_id = ?")
            params.append(int(filters['supplier_id']))
    else:
        # Unauthenticated / Admin
        if filters.get('supplier_id'):
            conditions.append("p.supplier_user_id = ?")
            params.append(int(filters['supplier_id']))

    # Search query across common_name, botanical_name, description
    search = filters.get('search') or filters.get('q')
    if search and str(search).strip():
        term = f"%{str(search).strip()}%"
        conditions.append("(p.common_name LIKE ? OR p.botanical_name LIKE ? OR p.description LIKE ?)")
        params.extend([term, term, term])

    # Category filter
    category = filters.get('category')
    if category and str(category).strip():
        cat_clean = str(category).strip().upper()
        conditions.append("p.category = ?")
        params.append(cat_clean)

    # Status filter
    status = filters.get('status')
    if status and str(status).strip():
        st_clean = str(status).strip().upper()
        conditions.append("p.status = ?")
        params.append(st_clean)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT p.*,
               u.username AS supplier_username,
               u.business_name AS supplier_name
        FROM plants p
        JOIN users u ON p.supplier_user_id = u.id
        {where_clause}
        ORDER BY p.common_name ASC
    """

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_plant_by_id(conn, plant_id, user=None):
    """
    Retrieves full details of a specific plant record by ID.
    Enforces privacy guard: one supplier cannot inspect another supplier's DISCONTINUED records.
    """
    query = """
        SELECT p.*,
               u.username AS supplier_username,
               u.business_name AS supplier_name
        FROM plants p
        JOIN users u ON p.supplier_user_id = u.id
        WHERE p.id = ?
    """
    row = conn.execute(query, (plant_id,)).fetchone()
    if not row:
        return None

    plant = dict(row)

    # Privacy check for discontinued records
    if user and user.get('role') == 'SUPPLIER':
        if plant['supplier_user_id'] != user['id'] and plant['status'] == 'DISCONTINUED':
            raise PermissionError("Access forbidden: This plant inventory record is discontinued and private to its supplier.")
    elif user and user.get('role') == 'NURSERY':
        if plant['status'] == 'DISCONTINUED':
            return None  # Discontinued items hidden from nursery view

    return plant


def create_plant(conn, user, data):
    """
    Validates and persists a new wholesale plant catalog item.
    Enforces that supplier_user_id is strictly derived from the authenticated session.
    """
    if not user or not user.get('id'):
        raise PermissionError("Authentication required.")

    if user.get('role') != 'SUPPLIER':
        raise PermissionError("Forbidden: Only registered suppliers can add plants to the catalog.")

    validated = validate_plant_data(data, is_update=False)

    cursor = conn.execute(
        """INSERT INTO plants
           (common_name, botanical_name, category, container_size, unit,
            unit_price, stock_qty, min_order_qty, description, status, supplier_user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            validated['common_name'],
            validated['botanical_name'],
            validated['category'],
            validated['container_size'],
            validated['unit'],
            validated['unit_price'],
            validated['stock_qty'],
            validated['min_order_qty'],
            validated['description'],
            validated['status'],
            user['id']  # Strictly session derived; client-supplied supplier_id is ignored
        )
    )

    new_id = cursor.lastrowid
    return get_plant_by_id(conn, new_id, user)


def update_plant(conn, plant_id, user, data):
    """
    Validates and updates an existing plant record.
    Enforces ownership: a supplier can ONLY update their own plant records.
    """
    if not user or not user.get('id'):
        raise PermissionError("Authentication required.")

    if user.get('role') != 'SUPPLIER':
        raise PermissionError("Forbidden: Only suppliers can modify plant catalog records.")

    existing_row = conn.execute("SELECT * FROM plants WHERE id = ?", (plant_id,)).fetchone()
    if not existing_row:
        raise ValueError(f"Plant #{plant_id} not found.")

    existing = dict(existing_row)

    # Ownership enforcement
    if existing['supplier_user_id'] != user['id']:
        raise PermissionError("Forbidden: You cannot modify another supplier's plant inventory.")

    validated = validate_plant_data(data, is_update=True, existing=existing)

    conn.execute(
        """UPDATE plants
           SET common_name = ?,
               botanical_name = ?,
               category = ?,
               container_size = ?,
               unit = ?,
               unit_price = ?,
               stock_qty = ?,
               min_order_qty = ?,
               description = ?,
               status = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ? AND supplier_user_id = ?""",
        (
            validated['common_name'],
            validated['botanical_name'],
            validated['category'],
            validated['container_size'],
            validated['unit'],
            validated['unit_price'],
            validated['stock_qty'],
            validated['min_order_qty'],
            validated['description'],
            validated['status'],
            plant_id,
            user['id']
        )
    )

    return get_plant_by_id(conn, plant_id, user)
