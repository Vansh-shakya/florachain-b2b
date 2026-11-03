"""
FloraChain B2B — Digital Deal Agreement & Payment Terms Service
Stage: Digital Deal Agreement & Payment Terms

Enforces:
- Unique agreement reference per version (e.g. AGR-8801-v1)
- Server-side calculation & validation of advance and balance amounts
- Due date and late-payment interest terms (rate, calculation basis, grace period)
- Independent dual approval (Supplier and Nursery)
- Immutability of agreed terms with versioned amendment workflows
- Append-only audit logging using Platform Core audit_events
- Legal clarity: distinct in-app commercial approval (not asymmetric PKI digital signature)
"""

import json
from datetime import datetime, timedelta
from app.services.audit_service import log_audit_event

VALID_BASES = ('ANNUAL_SIMPLE', 'MONTHLY_SIMPLE', 'DAILY_SIMPLE', 'NONE')
LEGAL_DISCLAIMER = (
    "Recorded In-App Commercial Assent: This record logs mutual electronic assent and platform "
    "timestamps for B2B payment terms. It does not constitute an asymmetric cryptographic digital signature."
)

def validate_and_calculate_terms(data, order=None):
    """
    Validates deal terms and calculates advance, balance, and interest parameters.
    Returns a sanitized dictionary of calculated fields, or raises ValueError.
    """
    # 1. Quantity & Pricing
    if order:
        default_qty = order['ordered_qty']
        default_price = order['unit_price']
        default_variety = order['variety']
    else:
        default_qty = None
        default_price = None
        default_variety = ''

    try:
        qty_raw = data.get('quantity', default_qty)
        qty = int(qty_raw)
        if qty <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("Plant quantity must be a positive whole number.")

    try:
        price_raw = data.get('unit_price', default_price)
        price = float(price_raw)
        if price <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("Unit price must be a positive currency amount.")

    total_order_value = round(qty * price, 2)
    variety = str(data.get('plant_variety', default_variety)).strip()
    if not variety:
        variety = "Wholesale Nursery Batch"

    # 2. Advance & Balance Calculation
    adv_pct = data.get('advance_percentage')
    adv_amt = data.get('advance_amount')

    if adv_pct is not None and adv_pct != '':
        try:
            adv_pct = float(adv_pct)
            if adv_pct < 0.0 or adv_pct > 100.0:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError("Advance percentage must be a number between 0% and 100%.")
        adv_amt = round(total_order_value * (adv_pct / 100.0), 2)
    elif adv_amt is not None and adv_amt != '':
        try:
            adv_amt = float(adv_amt)
            if adv_amt < 0.0 or adv_amt > total_order_value:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError(f"Advance amount must be between ₹0.00 and total order value (₹{total_order_value:,.2f}).")
        adv_pct = round((adv_amt / total_order_value) * 100.0, 2) if total_order_value > 0 else 0.0
    else:
        # Default 20% upfront advance
        adv_pct = 20.0
        adv_amt = round(total_order_value * 0.20, 2)

    bal_amt = round(total_order_value - adv_amt, 2)
    # Ensure exact sum matching
    if round(adv_amt + bal_amt, 2) != total_order_value:
        bal_amt = round(total_order_value - adv_amt, 2)

    # 3. Payment Period & Due Date
    try:
        period_days = int(data.get('payment_period_days', 10))
        if period_days < 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("Payment period days must be a non-negative whole number.")

    due_date_str = data.get('payment_due_date')
    if due_date_str:
        try:
            # Validate ISO YYYY-MM-DD
            parsed_date = datetime.strptime(str(due_date_str).strip(), '%Y-%m-%d').date()
            payment_due_date = parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            raise ValueError("Payment due date must be in valid YYYY-MM-DD format.")
    else:
        # Auto-compute from today + period_days
        payment_due_date = (datetime.now().date() + timedelta(days=period_days)).strftime('%Y-%m-%d')

    # 4. Late-Payment Interest Terms
    try:
        interest_rate = float(data.get('interest_rate_pct', 0.0))
        if interest_rate < 0.0:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("Late-payment interest rate must be 0% or a positive percentage.")

    calc_basis = str(data.get('interest_calculation_basis', 'ANNUAL_SIMPLE')).upper().strip()
    if calc_basis not in VALID_BASES:
        raise ValueError(f"Interest calculation basis must be one of: {', '.join(VALID_BASES)}")

    try:
        grace_days = int(data.get('interest_grace_period_days', 0))
        if grace_days < 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("Interest grace period must be a non-negative whole number of days.")

    notes = str(data.get('notes', '')).strip()

    return {
        "plant_variety": variety,
        "quantity": qty,
        "unit_price": price,
        "total_order_value": total_order_value,
        "advance_percentage": adv_pct,
        "advance_amount": adv_amt,
        "balance_amount": bal_amt,
        "payment_due_date": payment_due_date,
        "payment_period_days": period_days,
        "interest_rate_pct": interest_rate,
        "interest_calculation_basis": calc_basis,
        "interest_grace_period_days": grace_days,
        "notes": notes
    }

def create_deal_agreement(conn, order_id, terms_data, creator_user, ip_address='127.0.0.1', auto_approve=True):
    """
    Creates a new digital deal agreement for a specific order.
    """
    if not creator_user or not creator_user.get('id'):
        raise PermissionError("Authentication required.")

    # 1. Fetch order
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        raise ValueError(f"Order #{order_id} does not exist.")

    # 2. Authorization: Creator must be either supplier or nursery of this order
    creator_id = creator_user['id']
    creator_role = creator_user.get('role', '')

    if creator_id == order['supplier_user_id']:
        party_role = 'SUPPLIER'
    elif creator_id == order['nursery_user_id']:
        party_role = 'NURSERY'
    elif creator_role == 'ADMIN':
        raise PermissionError("Administrators cannot create commercial deal agreements on behalf of trading parties.")
    else:
        raise PermissionError(f"User is not an authorized party for Order #{order_id}.")

    if creator_role != party_role:
        raise PermissionError(f"Role mismatch: User role is '{creator_role}', but required party role is '{party_role}'.")

    # 3. Check for existing active agreed agreement
    existing_agreed = conn.execute(
        "SELECT id, agreement_ref, version FROM deal_agreements WHERE order_id = ? AND status = 'AGREED'",
        (order_id,)
    ).fetchone()
    if existing_agreed:
        raise ValueError(
            f"An active agreed agreement ({existing_agreed['agreement_ref']}) already exists for Order #{order_id}. "
            "Please create a versioned amendment to modify terms."
        )

    # 4. Calculate and validate terms
    terms = validate_and_calculate_terms(terms_data, order)

    # 5. Version numbering
    count_row = conn.execute(
        "SELECT COUNT(*) as c FROM deal_agreements WHERE order_id = ?",
        (order_id,)
    ).fetchone()
    version = (count_row['c'] if count_row else 0) + 1
    agreement_ref = f"AGR-{order_id}-v{version}"

    status = 'PENDING_COUNTERPARTY_APPROVAL' if auto_approve else 'DRAFT'

    cursor = conn.execute(
        """INSERT INTO deal_agreements 
           (agreement_ref, order_id, version, supplier_user_id, nursery_user_id, plant_variety,
            quantity, unit_price, total_order_value, advance_percentage, advance_amount, balance_amount,
            payment_due_date, payment_period_days, interest_rate_pct, interest_calculation_basis,
            interest_grace_period_days, notes, status, created_by_user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            agreement_ref, order_id, version, order['supplier_user_id'], order['nursery_user_id'],
            terms['plant_variety'], terms['quantity'], terms['unit_price'], terms['total_order_value'],
            terms['advance_percentage'], terms['advance_amount'], terms['balance_amount'],
            terms['payment_due_date'], terms['payment_period_days'], terms['interest_rate_pct'],
            terms['interest_calculation_basis'], terms['interest_grace_period_days'],
            terms['notes'], status, creator_id
        )
    )
    agreement_id = cursor.lastrowid

    snapshot = json.dumps({
        "agreement_ref": agreement_ref,
        "order_id": order_id,
        "version": version,
        "total_order_value": terms['total_order_value'],
        "advance_amount": terms['advance_amount'],
        "balance_amount": terms['balance_amount'],
        "payment_due_date": terms['payment_due_date'],
        "interest_rate_pct": terms['interest_rate_pct'],
        "created_by": creator_user['username']
    })

    # Log agreement creation audit event
    log_audit_event(
        conn,
        event_type="AGREEMENT_CREATED",
        order_id=order_id,
        actor_user_id=creator_id,
        actor_role=party_role,
        after_state=json.loads(snapshot),
        justification=f"Created digital deal agreement {agreement_ref}.",
        ip_address=ip_address
    )

    # 6. Auto-approve for the creator if requested
    if auto_approve:
        conn.execute(
            """INSERT INTO agreement_approvals 
               (agreement_id, party_role, user_id, approval_type, terms_snapshot_json, notes, ip_address)
               VALUES (?, ?, ?, 'IN_APP_CLICK', ?, ?, ?)""",
            (agreement_id, party_role, creator_id, snapshot, "Initial terms agreed upon agreement creation.", ip_address)
        )
        log_audit_event(
            conn,
            event_type=f"AGREEMENT_APPROVED_{party_role}",
            order_id=order_id,
            actor_user_id=creator_id,
            actor_role=party_role,
            after_state=json.loads(snapshot),
            justification=f"{party_role} registered initial in-app commercial approval for {agreement_ref}.",
            ip_address=ip_address
        )

    return get_agreement_details(conn, agreement_id)

def get_agreement_details(conn, agreement_id_or_ref):
    """
    Retrieves full details of a deal agreement, including parties, terms, approvals, and legal notice.
    """
    if isinstance(agreement_id_or_ref, int) or (isinstance(agreement_id_or_ref, str) and agreement_id_or_ref.isdigit()):
        clause = "da.id = ?"
        param = int(agreement_id_or_ref)
    else:
        clause = "da.agreement_ref = ?"
        param = str(agreement_id_or_ref)

    row = conn.execute(f"""
        SELECT da.*,
               o.variety as order_variety, o.ordered_qty as order_qty, o.unit_price as order_price,
               o.truck_no, o.driver_info, o.status as order_status,
               s.username as supplier_username, s.business_name as supplier_name, s.email as supplier_email,
               n.username as nursery_username, n.business_name as nursery_name, n.email as nursery_email,
               u.username as creator_username, u.business_name as creator_business
        FROM deal_agreements da
        JOIN orders o ON da.order_id = o.id
        JOIN users s ON da.supplier_user_id = s.id
        JOIN users n ON da.nursery_user_id = n.id
        JOIN users u ON da.created_by_user_id = u.id
        WHERE {clause}
    """, (param,)).fetchone()

    if not row:
        return None

    agreement = dict(row)

    # Fetch approvals
    approvals_rows = conn.execute("""
        SELECT ap.*, u.username, u.business_name
        FROM agreement_approvals ap
        JOIN users u ON ap.user_id = u.id
        WHERE ap.agreement_id = ?
        ORDER BY ap.approved_at ASC
    """, (agreement['id'],)).fetchall()

    approvals = []
    supplier_approved = False
    supplier_approval = None
    nursery_approved = False
    nursery_approval = None

    for app in approvals_rows:
        app_dict = dict(app)
        try:
            app_dict['terms_snapshot'] = json.loads(app_dict['terms_snapshot_json'])
        except (TypeError, ValueError):
            app_dict['terms_snapshot'] = {}
        approvals.append(app_dict)

        if app_dict['party_role'] == 'SUPPLIER':
            supplier_approved = True
            supplier_approval = app_dict
        elif app_dict['party_role'] == 'NURSERY':
            nursery_approved = True
            nursery_approval = app_dict

    agreement['approvals'] = approvals
    agreement['supplier_approved'] = supplier_approved
    agreement['supplier_approval'] = supplier_approval
    agreement['nursery_approved'] = nursery_approved
    agreement['nursery_approval'] = nursery_approval
    agreement['is_agreed'] = (agreement['status'] == 'AGREED')
    agreement['legal_disclaimer'] = LEGAL_DISCLAIMER

    return agreement

def list_agreements_for_user(conn, user, order_id=None):
    """
    Returns deal agreements viewable by the user based on role and order assignment.
    """
    if not user:
        return []

    conditions = []
    params = []

    if user['role'] == 'SUPPLIER':
        conditions.append("da.supplier_user_id = ?")
        params.append(user['id'])
    elif user['role'] == 'NURSERY':
        conditions.append("da.nursery_user_id = ?")
        params.append(user['id'])
    # ADMIN can see all

    if order_id:
        conditions.append("da.order_id = ?")
        params.append(order_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT da.*,
               o.variety as order_variety,
               s.username as supplier_username, s.business_name as supplier_name,
               n.username as nursery_username, n.business_name as nursery_name
        FROM deal_agreements da
        JOIN orders o ON da.order_id = o.id
        JOIN users s ON da.supplier_user_id = s.id
        JOIN users n ON da.nursery_user_id = n.id
        {where_clause}
        ORDER BY da.created_at DESC, da.id DESC
    """
    rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        results.append(get_agreement_details(conn, r['id']))
    return results

def approve_deal_agreement(conn, agreement_id, user, notes='', ip_address='127.0.0.1'):
    """
    Independent party approval of a deal agreement.
    Atomically sets status = 'AGREED' when both Supplier and Nursery approve.
    """
    if not user or not user.get('id'):
        raise PermissionError("Authentication required.")

    agreement = conn.execute("SELECT * FROM deal_agreements WHERE id = ?", (agreement_id,)).fetchone()
    if not agreement:
        raise ValueError(f"Deal agreement #{agreement_id} not found.")

    if agreement['status'] == 'AGREED':
        raise ValueError(f"Agreement {agreement['agreement_ref']} is already agreed and permanently finalized.")

    if agreement['status'] == 'CANCELLED':
        raise ValueError("Cannot approve a cancelled agreement.")

    # Determine party role
    user_id = user['id']
    user_role = user.get('role', '')

    if user_id == agreement['supplier_user_id']:
        party_role = 'SUPPLIER'
    elif user_id == agreement['nursery_user_id']:
        party_role = 'NURSERY'
    elif user_role == 'ADMIN':
        raise PermissionError("Security Violation: Administrators cannot impersonate either party or satisfy agreement approvals.")
    else:
        raise PermissionError("User is not an authorized party for this deal agreement.")

    if user_role != party_role:
        raise PermissionError(f"Role mismatch: Active role '{user_role}' cannot approve on behalf of '{party_role}'.")

    # Check for duplicate approval
    existing = conn.execute(
        "SELECT id, approved_at FROM agreement_approvals WHERE agreement_id = ? AND party_role = ?",
        (agreement_id, party_role)
    ).fetchone()
    if existing:
        raise ValueError(f"{party_role} has already approved agreement {agreement['agreement_ref']} at {existing['approved_at']}.")

    # Snapshot accepted terms
    terms_snapshot = {
        "agreement_ref": agreement['agreement_ref'],
        "order_id": agreement['order_id'],
        "version": agreement['version'],
        "plant_variety": agreement['plant_variety'],
        "quantity": agreement['quantity'],
        "unit_price": agreement['unit_price'],
        "total_order_value": agreement['total_order_value'],
        "advance_percentage": agreement['advance_percentage'],
        "advance_amount": agreement['advance_amount'],
        "balance_amount": agreement['balance_amount'],
        "payment_due_date": agreement['payment_due_date'],
        "payment_period_days": agreement['payment_period_days'],
        "interest_rate_pct": agreement['interest_rate_pct'],
        "interest_calculation_basis": agreement['interest_calculation_basis'],
        "interest_grace_period_days": agreement['interest_grace_period_days'],
        "notes": agreement['notes'],
        "approved_by_username": user['username'],
        "approved_by_business": user['business_name'],
        "approval_type": "IN_APP_CLICK",
        "legal_notice": LEGAL_DISCLAIMER
    }
    snapshot_json = json.dumps(terms_snapshot)

    # Insert approval
    conn.execute(
        """INSERT INTO agreement_approvals 
           (agreement_id, party_role, user_id, approval_type, terms_snapshot_json, notes, ip_address)
           VALUES (?, ?, ?, 'IN_APP_CLICK', ?, ?, ?)""",
        (agreement_id, party_role, user_id, snapshot_json, (notes or '').strip(), ip_address)
    )

    # Check if counterparty has approved
    counterparty_role = 'NURSERY' if party_role == 'SUPPLIER' else 'SUPPLIER'
    counterparty_approval = conn.execute(
        "SELECT id FROM agreement_approvals WHERE agreement_id = ? AND party_role = ?",
        (agreement_id, counterparty_role)
    ).fetchone()

    before_state = {
        "status": agreement['status'],
        "agreed_at": agreement['agreed_at']
    }

    if counterparty_approval:
        # Both parties have now approved! Transition to AGREED
        conn.execute(
            """UPDATE deal_agreements 
               SET status = 'AGREED', agreed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (agreement_id,)
        )

        after_state = {
            "agreement_ref": agreement['agreement_ref'],
            "status": "AGREED",
            "agreed_at": datetime.now().isoformat(),
            "final_approver": user['username'],
            "final_role": party_role
        }

        log_audit_event(
            conn,
            event_type="AGREEMENT_AGREED",
            order_id=agreement['order_id'],
            actor_user_id=user_id,
            actor_role=party_role,
            before_state=before_state,
            after_state=after_state,
            justification=f"Both parties ({party_role} & {counterparty_role}) approved. Agreement {agreement['agreement_ref']} permanently agreed.",
            ip_address=ip_address
        )
    else:
        # One party approved; still pending counterparty
        conn.execute(
            """UPDATE deal_agreements 
               SET status = 'PENDING_COUNTERPARTY_APPROVAL', updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (agreement_id,)
        )

        after_state = {
            "agreement_ref": agreement['agreement_ref'],
            "status": "PENDING_COUNTERPARTY_APPROVAL",
            "approved_by": party_role
        }

        log_audit_event(
            conn,
            event_type=f"AGREEMENT_APPROVED_{party_role}",
            order_id=agreement['order_id'],
            actor_user_id=user_id,
            actor_role=party_role,
            before_state=before_state,
            after_state=after_state,
            justification=f"{party_role} registered approval for {agreement['agreement_ref']}; awaiting {counterparty_role}.",
            ip_address=ip_address
        )

    return get_agreement_details(conn, agreement_id)

def create_deal_amendment(conn, agreement_id, revised_terms, user, reason, ip_address='127.0.0.1'):
    """
    Creates a versioned amendment from an agreed agreement.
    Preserves original agreement intact and begins a new approval cycle for version (N+1).
    """
    if not user or not user.get('id'):
        raise PermissionError("Authentication required.")

    if not reason or not str(reason).strip():
        raise ValueError("A clear reason / justification is required to amend agreed terms.")

    orig = conn.execute("SELECT * FROM deal_agreements WHERE id = ?", (agreement_id,)).fetchone()
    if not orig:
        raise ValueError(f"Agreement #{agreement_id} not found.")

    if orig['status'] != 'AGREED':
        raise ValueError(
            f"Only finalized 'AGREED' agreements can be amended. Current status is '{orig['status']}'. "
            "Unfinalized agreements should be updated directly."
        )

    # Check user is authorized party
    user_id = user['id']
    user_role = user.get('role', '')

    if user_id == orig['supplier_user_id']:
        party_role = 'SUPPLIER'
    elif user_id == orig['nursery_user_id']:
        party_role = 'NURSERY'
    elif user_role == 'ADMIN':
        raise PermissionError("Administrators cannot create amendments on behalf of trading parties.")
    else:
        raise PermissionError("User is not an authorized party for this agreement.")

    if user_role != party_role:
        raise PermissionError(f"Role mismatch: '{user_role}' cannot create amendment for '{party_role}'.")

    # Calculate revised terms
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (orig['order_id'],)).fetchone()
    terms = validate_and_calculate_terms(revised_terms, order)

    new_version = orig['version'] + 1
    new_ref = f"AGR-{orig['order_id']}-v{new_version}"

    cursor = conn.execute(
        """INSERT INTO deal_agreements 
           (agreement_ref, order_id, version, supplier_user_id, nursery_user_id, plant_variety,
            quantity, unit_price, total_order_value, advance_percentage, advance_amount, balance_amount,
            payment_due_date, payment_period_days, interest_rate_pct, interest_calculation_basis,
            interest_grace_period_days, notes, status, created_by_user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_COUNTERPARTY_APPROVAL', ?)""",
        (
            new_ref, orig['order_id'], new_version, orig['supplier_user_id'], orig['nursery_user_id'],
            terms['plant_variety'], terms['quantity'], terms['unit_price'], terms['total_order_value'],
            terms['advance_percentage'], terms['advance_amount'], terms['balance_amount'],
            terms['payment_due_date'], terms['payment_period_days'], terms['interest_rate_pct'],
            terms['interest_calculation_basis'], terms['interest_grace_period_days'],
            terms['notes'], user_id
        )
    )
    new_id = cursor.lastrowid

    # Auto-approve for the amending party
    snapshot = json.dumps({
        "agreement_ref": new_ref,
        "order_id": orig['order_id'],
        "version": new_version,
        "total_order_value": terms['total_order_value'],
        "advance_amount": terms['advance_amount'],
        "balance_amount": terms['balance_amount'],
        "payment_due_date": terms['payment_due_date'],
        "interest_rate_pct": terms['interest_rate_pct'],
        "amended_by": user['username'],
        "amendment_reason": str(reason).strip()
    })

    conn.execute(
        """INSERT INTO agreement_approvals 
           (agreement_id, party_role, user_id, approval_type, terms_snapshot_json, notes, ip_address)
           VALUES (?, ?, ?, 'IN_APP_CLICK', ?, ?, ?)""",
        (new_id, party_role, user_id, snapshot, f"Amendment proposed: {reason}", ip_address)
    )

    before_state = {
        "original_agreement_ref": orig['agreement_ref'],
        "version": orig['version'],
        "total_order_value": orig['total_order_value'],
        "advance_amount": orig['advance_amount'],
        "balance_amount": orig['balance_amount'],
        "payment_due_date": orig['payment_due_date'],
        "interest_rate_pct": orig['interest_rate_pct']
    }

    log_audit_event(
        conn,
        event_type="AGREEMENT_AMENDMENT_CREATED",
        order_id=orig['order_id'],
        actor_user_id=user_id,
        actor_role=party_role,
        before_state=before_state,
        after_state=json.loads(snapshot),
        justification=f"Created versioned amendment {new_ref} for {orig['order_id']}. Reason: {reason}",
        ip_address=ip_address
    )

    return get_agreement_details(conn, new_id)

def update_draft_agreement(conn, agreement_id, revised_terms, user, ip_address='127.0.0.1'):
    """
    Modifies an unfinalized (DRAFT or PENDING_COUNTERPARTY_APPROVAL) deal agreement.
    Ordinary edits on 'AGREED' records are strictly rejected to preserve agreed terms.
    """
    if not user or not user.get('id'):
        raise PermissionError("Authentication required.")

    agreement = conn.execute("SELECT * FROM deal_agreements WHERE id = ?", (agreement_id,)).fetchone()
    if not agreement:
        raise ValueError(f"Agreement #{agreement_id} not found.")

    if agreement['status'] == 'AGREED':
        raise PermissionError(
            f"Agreement {agreement['agreement_ref']} is already agreed and permanently locked. "
            "Ordinary edits are prohibited. Please create a versioned amendment."
        )

    user_id = user['id']
    user_role = user.get('role', '')

    if user_id == agreement['supplier_user_id']:
        party_role = 'SUPPLIER'
    elif user_id == agreement['nursery_user_id']:
        party_role = 'NURSERY'
    else:
        raise PermissionError("User is not an authorized party for this agreement.")

    if user_role != party_role:
        raise PermissionError(f"Role mismatch: '{user_role}' cannot edit agreement for '{party_role}'.")

    order = conn.execute("SELECT * FROM orders WHERE id = ?", (agreement['order_id'],)).fetchone()
    terms = validate_and_calculate_terms(revised_terms, order)

    before_state = {
        "total_order_value": agreement['total_order_value'],
        "advance_amount": agreement['advance_amount'],
        "balance_amount": agreement['balance_amount'],
        "payment_due_date": agreement['payment_due_date'],
        "interest_rate_pct": agreement['interest_rate_pct']
    }

    # Reset any prior approvals since terms have changed
    conn.execute("DELETE FROM agreement_approvals WHERE agreement_id = ?", (agreement_id,))

    conn.execute(
        """UPDATE deal_agreements 
           SET plant_variety = ?, quantity = ?, unit_price = ?, total_order_value = ?,
               advance_percentage = ?, advance_amount = ?, balance_amount = ?,
               payment_due_date = ?, payment_period_days = ?, interest_rate_pct = ?,
               interest_calculation_basis = ?, interest_grace_period_days = ?,
               notes = ?, status = 'PENDING_COUNTERPARTY_APPROVAL', updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (
            terms['plant_variety'], terms['quantity'], terms['unit_price'], terms['total_order_value'],
            terms['advance_percentage'], terms['advance_amount'], terms['balance_amount'],
            terms['payment_due_date'], terms['payment_period_days'], terms['interest_rate_pct'],
            terms['interest_calculation_basis'], terms['interest_grace_period_days'],
            terms['notes'], agreement_id
        )
    )

    # Re-register editor's approval
    snapshot = json.dumps({
        "agreement_ref": agreement['agreement_ref'],
        "order_id": agreement['order_id'],
        "version": agreement['version'],
        "total_order_value": terms['total_order_value'],
        "advance_amount": terms['advance_amount'],
        "balance_amount": terms['balance_amount'],
        "payment_due_date": terms['payment_due_date'],
        "interest_rate_pct": terms['interest_rate_pct'],
        "updated_by": user['username']
    })

    conn.execute(
        """INSERT INTO agreement_approvals 
           (agreement_id, party_role, user_id, approval_type, terms_snapshot_json, notes, ip_address)
           VALUES (?, ?, ?, 'IN_APP_CLICK', ?, 'Terms updated by party; re-assented.', ?)""",
        (agreement_id, party_role, user_id, snapshot, ip_address)
    )

    log_audit_event(
        conn,
        event_type="AGREEMENT_UPDATED",
        order_id=agreement['order_id'],
        actor_user_id=user_id,
        actor_role=party_role,
        before_state=before_state,
        after_state=json.loads(snapshot),
        justification=f"Terms updated for {agreement['agreement_ref']}; re-assented by {party_role}.",
        ip_address=ip_address
    )

    return get_agreement_details(conn, agreement_id)
