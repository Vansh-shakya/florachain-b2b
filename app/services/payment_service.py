"""
FloraChain B2B — Wholesale Payment Recording & Outstanding Balance Engine
Phase 9: Payment Management, Advance Tracking, Overpayment Prevention & Audit Reversals

Enforces:
- Recording payments against issued commercial invoices with frozen historical totals
- High-precision decimal arithmetic (Decimal / paise rounding) to prevent floating-point discrepancies
- Multiple partial payments per invoice
- Real-time outstanding balance calculation: max(0.00, invoice_total - sum(active_allocations))
- Strict overpayment prevention: payment amount cannot exceed invoice outstanding balance
- Advance payment tracking: unallocated balance tracking and subsequent invoice allocation
- Duplicate payment reference prevention: rejects duplicate transaction/reference numbers
- Non-destructive auditable reversals: mark status = 'REVERSED' with reason and audit trail
- Role-based data isolation: Supplier vs Nursery vs Admin
- Append-only audit trail logging for all payment events
"""

import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from app.services.audit_service import log_audit_event


def quantize_currency(val):
    """
    Safely converts a number, float, or string to a Decimal with 2 decimal places.
    Uses ROUND_HALF_UP to match standard commercial banking rounding.
    """
    if val is None:
        return Decimal('0.00')
    if isinstance(val, Decimal):
        return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def generate_next_payment_number(conn):
    """
    Generates a sequential human-friendly payment number (e.g. PAY-2026-9001).
    Guarantees uniqueness across the platform.
    """
    current_year = datetime.now().year
    prefix = f"PAY-{current_year}-"
    rows = conn.execute("SELECT payment_number FROM payments WHERE payment_number LIKE ?", (f"{prefix}%",)).fetchall()
    highest = 9000
    for r in rows:
        num_part = r['payment_number'].replace(prefix, '')
        if num_part.isdigit():
            val = int(num_part)
            if val > highest:
                highest = val
    return f"{prefix}{highest + 1}"


def get_invoice_payment_summary(conn, invoice_id_or_number):
    """
    Calculates the financial status and payment summary for an invoice:
    - Invoiced Total (frozen from invoice record)
    - Total Payments Received (sum of active allocations)
    - Outstanding Balance (invoiced total - total payments received)
    - Payment Status: 'UNPAID', 'PARTIALLY_PAID', 'PAID'
    """
    inv = conn.execute(
        """SELECT * FROM invoices WHERE id = ? OR invoice_number = ?""",
        (invoice_id_or_number, invoice_id_or_number)
    ).fetchone()

    if not inv:
        return None

    inv_dict = dict(inv)
    inv_total = quantize_currency(inv_dict['total_amount'])

    allocations_rows = conn.execute(
        """SELECT a.*, p.payment_number, p.payment_date, p.payment_method, p.reference_number, p.status as payment_status
           FROM payment_allocations a
           JOIN payments p ON a.payment_id = p.id
           WHERE a.invoice_id = ? AND a.status = 'ACTIVE' AND p.status = 'RECORDED'
           ORDER BY a.allocated_at ASC, a.id ASC""",
        (inv_dict['id'],)
    ).fetchall()

    allocations = [dict(r) for r in allocations_rows]
    total_paid = quantize_currency(sum(Decimal(str(a['amount'])) for a in allocations))
    outstanding = max(Decimal('0.00'), inv_total - total_paid)

    if total_paid == Decimal('0.00'):
        status = 'UNPAID'
    elif total_paid < inv_total:
        status = 'PARTIALLY_PAID'
    else:
        status = 'PAID'

    return {
        "invoice_id": inv_dict['id'],
        "invoice_number": inv_dict['invoice_number'],
        "order_id": inv_dict['order_id'],
        "total_amount": float(inv_total),
        "total_paid": float(total_paid),
        "outstanding_balance": float(outstanding),
        "payment_status": status,
        "allocations_count": len(allocations),
        "allocations": allocations
    }


def record_payment(conn, payment_data, actor_user, ip_address="127.0.0.1"):
    """
    Records an incoming payment or advance and allocates funds:
    - Enforces positive amount > 0
    - Enforces valid payment method (BANK_TRANSFER, UPI, CHEQUE, CASH, OTHER)
    - Validates reference number uniqueness to prevent duplicate submissions
    - Prevents overpayment: payment cannot exceed invoice outstanding balance
    - Atomic database execution
    - Immutable audit trail logging
    """
    if not actor_user:
        raise PermissionError("Authentication required to record a payment.")

    actor_role = actor_user.get('role')
    if actor_role not in ('SUPPLIER', 'ADMIN'):
        raise PermissionError("Only wholesale suppliers or platform administrators can record payment receipts.")

    # 1. Amount Validation
    raw_amount = payment_data.get('amount')
    if raw_amount is None:
        raise ValueError("Payment amount is required.")
    try:
        amount_dec = quantize_currency(raw_amount)
    except Exception:
        raise ValueError(f"Invalid payment amount: '{raw_amount}'. Must be a valid numerical value.")

    if amount_dec <= Decimal('0.00'):
        raise ValueError(f"Payment amount must be strictly positive (> ₹0.00). Received: ₹{amount_dec:.2f}")

    # 2. Reference Number Validation & Duplicate Prevention
    ref_num = str(payment_data.get('reference_number') or '').strip()
    if not ref_num:
        raise ValueError("Transaction or reference number (e.g. UTR, Cheque No, Bank Ref) is required.")

    # Check for duplicate reference among active (non-reversed) payments
    existing_ref = conn.execute(
        "SELECT id, payment_number FROM payments WHERE reference_number = ? AND status = 'RECORDED'",
        (ref_num,)
    ).fetchone()
    if existing_ref:
        raise ValueError(f"A payment with transaction reference '{ref_num}' has already been recorded (#{existing_ref['payment_number']}). Duplicate submissions are rejected.")

    # 3. Payment Method Validation
    allowed_methods = ('BANK_TRANSFER', 'UPI', 'CHEQUE', 'CASH', 'OTHER')
    method = str(payment_data.get('payment_method') or 'BANK_TRANSFER').strip().upper()
    if method not in allowed_methods:
        raise ValueError(f"Invalid payment method: '{method}'. Allowed methods: {', '.join(allowed_methods)}")

    # 4. Payment Date Validation
    pay_date = str(payment_data.get('payment_date') or '').strip()
    if not pay_date:
        pay_date = date.today().isoformat()
    else:
        try:
            datetime.strptime(pay_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid payment date format: '{pay_date}'. Expected YYYY-MM-DD.")

    payment_type = str(payment_data.get('payment_type') or 'INVOICE_PAYMENT').strip().upper()
    invoice_id = payment_data.get('invoice_id')
    order_id = payment_data.get('order_id')
    notes = str(payment_data.get('notes') or '').strip()

    # 5. Handle Invoicing Allocation vs Advance
    inv = None
    if invoice_id:
        inv = conn.execute(
            "SELECT * FROM invoices WHERE id = ? OR invoice_number = ?",
            (invoice_id, invoice_id)
        ).fetchone()
        if not inv:
            raise ValueError(f"Invoice '{invoice_id}' does not exist.")
        inv_dict = dict(inv)

        if inv_dict['status'] == 'CANCELLED':
            raise ValueError(f"Cannot record payment against cancelled Invoice #{inv_dict['invoice_number']}.")

        # Supplier isolation check
        if actor_role == 'SUPPLIER' and actor_user.get('id') != inv_dict['supplier_user_id']:
            raise PermissionError("Unauthorized: You can only record payments for your own wholesale invoices.")

        supplier_user_id = inv_dict['supplier_user_id']
        nursery_user_id = inv_dict['nursery_user_id']
        order_id = inv_dict['order_id']
        actual_inv_id = inv_dict['id']

        # Safe Balance Calculation & Overpayment Prevention
        summary = get_invoice_payment_summary(conn, actual_inv_id)
        outstanding = quantize_currency(summary['outstanding_balance'])

        if outstanding <= Decimal('0.00'):
            raise ValueError(f"Invoice #{inv_dict['invoice_number']} is already fully settled (Outstanding: ₹0.00). No further payments can be accepted.")

        if amount_dec > outstanding:
            raise ValueError(
                f"Overpayment rejected: Payment amount ₹{amount_dec:.2f} exceeds current outstanding balance of ₹{outstanding:.2f} on Invoice #{inv_dict['invoice_number']}."
            )

        unallocated_dec = Decimal('0.00')

    elif payment_type == 'ADVANCE_PAYMENT':
        if not order_id and not payment_data.get('nursery_user_id'):
            raise ValueError("Advance payment requires an associated Order ID or Nursery ID.")

        if order_id:
            ord_row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not ord_row:
                raise ValueError(f"Order '{order_id}' does not exist.")
            ord_dict = dict(ord_row)
            supplier_user_id = ord_dict['supplier_user_id']
            nursery_user_id = ord_dict['nursery_user_id']
        else:
            nursery_user_id = int(payment_data['nursery_user_id'])
            supplier_user_id = actor_user['id']

        actual_inv_id = None
        unallocated_dec = amount_dec

    else:
        raise ValueError("Payment requires either an invoice_id or payment_type='ADVANCE_PAYMENT'.")

    # 6. Generate Payment ID and Persist Transaction
    payment_number = generate_next_payment_number(conn)
    payment_id = payment_number

    conn.execute(
        """INSERT INTO payments
           (id, payment_number, invoice_id, order_id, supplier_user_id, nursery_user_id, amount,
            unallocated_amount, payment_date, payment_method, reference_number, payment_type,
            status, notes, created_by_user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'RECORDED', ?, ?)""",
        (payment_id, payment_number, actual_inv_id, order_id, supplier_user_id, nursery_user_id,
         float(amount_dec), float(unallocated_dec), pay_date, method, ref_num, payment_type,
         notes, actor_user['id'])
    )

    # 7. Record Allocation if applied to invoice
    if actual_inv_id:
        conn.execute(
            """INSERT INTO payment_allocations
               (payment_id, invoice_id, amount, status, notes, allocated_by_user_id)
               VALUES (?, ?, ?, 'ACTIVE', ?, ?)""",
            (payment_id, actual_inv_id, float(amount_dec), notes or f"Direct payment towards Invoice #{inv_dict['invoice_number']}", actor_user['id'])
        )

    # 8. Append Immutable Audit Event
    audit_event_type = "PAYMENT_RECORDED" if actual_inv_id else "ADVANCE_RECORDED"
    log_audit_event(
        conn,
        event_type=audit_event_type,
        order_id=order_id or "GENERAL",
        actor_user_id=actor_user['id'],
        actor_role=actor_role,
        before_state={"outstanding_balance": float(outstanding)} if inv else None,
        after_state={
            "payment_number": payment_number,
            "amount": float(amount_dec),
            "payment_method": method,
            "reference_number": ref_num,
            "invoice_id": actual_inv_id,
            "payment_type": payment_type,
            "new_outstanding_balance": float(outstanding - amount_dec) if inv else None
        },
        justification=notes or f"Wholesale payment receipt #{payment_number} recorded via {method}.",
        ip_address=ip_address
    )

    return get_payment_details(conn, payment_id, actor_user)


def allocate_advance_payment(conn, payment_id_or_number, invoice_id_or_number, amount_to_allocate, actor_user, ip_address="127.0.0.1"):
    """
    Allocates an unallocated advance payment to an issued invoice.
    Enforces:
    - Payment must exist, be an active advance, with unallocated_amount > 0
    - Invoice must exist, be ISSUED, and have an outstanding balance > 0
    - Amount cannot exceed either payment unallocated amount or invoice outstanding balance
    """
    if not actor_user or actor_user.get('role') not in ('SUPPLIER', 'ADMIN'):
        raise PermissionError("Unauthorized: Only wholesale suppliers or administrators can allocate advances.")

    pay = conn.execute(
        "SELECT * FROM payments WHERE id = ? OR payment_number = ?",
        (payment_id_or_number, payment_id_or_number)
    ).fetchone()
    if not pay:
        raise ValueError(f"Payment '{payment_id_or_number}' not found.")
    pay_dict = dict(pay)

    if pay_dict['status'] == 'REVERSED':
        raise ValueError("Cannot allocate funds from a reversed payment.")

    unallocated = quantize_currency(pay_dict['unallocated_amount'])
    if unallocated <= Decimal('0.00'):
        raise ValueError(f"Payment #{pay_dict['payment_number']} has no remaining unallocated balance (₹0.00).")

    try:
        alloc_dec = quantize_currency(amount_to_allocate)
    except Exception:
        raise ValueError(f"Invalid allocation amount '{amount_to_allocate}'. Must be a valid numerical value.")

    if alloc_dec <= Decimal('0.00'):
        raise ValueError("Allocated amount must be strictly greater than ₹0.00.")

    if alloc_dec > unallocated:
        raise ValueError(f"Requested allocation ₹{alloc_dec:.2f} exceeds available advance balance of ₹{unallocated:.2f}.")

    inv = conn.execute(
        "SELECT * FROM invoices WHERE id = ? OR invoice_number = ?",
        (invoice_id_or_number, invoice_id_or_number)
    ).fetchone()
    if not inv:
        raise ValueError(f"Invoice '{invoice_id_or_number}' not found.")
    inv_dict = dict(inv)

    if inv_dict['status'] == 'CANCELLED':
        raise ValueError(f"Cannot allocate advance to cancelled Invoice #{inv_dict['invoice_number']}.")

    # Multi-tenant Counterparty isolation check: payment and invoice must belong to the exact same counterparties
    if pay_dict['nursery_user_id'] != inv_dict['nursery_user_id']:
        raise ValueError(f"Cannot allocate advance payment #{pay_dict['payment_number']} to an invoice belonging to a different client nursery.")

    if pay_dict['supplier_user_id'] != inv_dict['supplier_user_id']:
        raise ValueError(f"Cannot allocate advance payment #{pay_dict['payment_number']} across different wholesale suppliers.")

    # Supplier isolation check
    if actor_user.get('role') == 'SUPPLIER' and actor_user.get('id') != inv_dict['supplier_user_id']:
        raise PermissionError("Unauthorized: You can only allocate payments to your own wholesale invoices.")

    summary = get_invoice_payment_summary(conn, inv_dict['id'])
    outstanding = quantize_currency(summary['outstanding_balance'])

    if outstanding <= Decimal('0.00'):
        raise ValueError(f"Invoice #{inv_dict['invoice_number']} is already fully settled.")

    if alloc_dec > outstanding:
        raise ValueError(f"Allocation of ₹{alloc_dec:.2f} exceeds invoice outstanding balance of ₹{outstanding:.2f}.")

    # Apply allocation
    conn.execute(
        """INSERT INTO payment_allocations
           (payment_id, invoice_id, amount, status, notes, allocated_by_user_id)
           VALUES (?, ?, ?, 'ACTIVE', ?, ?)""",
        (pay_dict['id'], inv_dict['id'], float(alloc_dec),
         f"Advance #{pay_dict['payment_number']} allocated to Invoice #{inv_dict['invoice_number']}", actor_user['id'])
    )

    new_unallocated = unallocated - alloc_dec
    conn.execute(
        "UPDATE payments SET unallocated_amount = ? WHERE id = ?",
        (float(new_unallocated), pay_dict['id'])
    )

    log_audit_event(
        conn,
        event_type="ADVANCE_ALLOCATED",
        order_id=inv_dict['order_id'],
        actor_user_id=actor_user['id'],
        actor_role=actor_user['role'],
        before_state={"unallocated_amount": float(unallocated), "outstanding_balance": float(outstanding)},
        after_state={"allocated_amount": float(alloc_dec), "remaining_advance": float(new_unallocated), "new_outstanding": float(outstanding - alloc_dec)},
        justification=f"Advance #{pay_dict['payment_number']} allocated to Invoice #{inv_dict['invoice_number']}.",
        ip_address=ip_address
    )

    return {
        "payment_id": pay_dict['id'],
        "invoice_id": inv_dict['id'],
        "allocated_amount": float(alloc_dec),
        "remaining_unallocated_advance": float(new_unallocated),
        "invoice_outstanding_balance": float(outstanding - alloc_dec)
    }


def reverse_payment(conn, payment_id_or_number, reversal_reason, actor_user, ip_address="127.0.0.1"):
    """
    Auditably reverses an existing payment:
    - Never deletes records; updates status to 'REVERSED'
    - Reverses all associated invoice allocations, restoring outstanding invoice balances
    - Logs detailed audit event with actor, timestamp, and justification
    """
    if not actor_user or actor_user.get('role') not in ('SUPPLIER', 'ADMIN'):
        raise PermissionError("Unauthorized: Only wholesale suppliers or administrators can reverse payment records.")

    reason = str(reversal_reason or '').strip()
    if len(reason) < 3:
        raise ValueError("A clear, substantive reversal reason is required (minimum 3 characters).")

    pay = conn.execute(
        "SELECT * FROM payments WHERE id = ? OR payment_number = ?",
        (payment_id_or_number, payment_id_or_number)
    ).fetchone()
    if not pay:
        raise ValueError(f"Payment '{payment_id_or_number}' not found.")
    pay_dict = dict(pay)

    if pay_dict['status'] == 'REVERSED':
        raise ValueError(f"Payment #{pay_dict['payment_number']} has already been reversed on {pay_dict['reversed_at']}.")

    # Supplier isolation check
    if actor_user.get('role') == 'SUPPLIER' and actor_user.get('id') != pay_dict['supplier_user_id']:
        raise PermissionError("Unauthorized: You can only reverse payment records belonging to your business.")

    # 1. Update Payment status
    conn.execute(
        """UPDATE payments 
           SET status = 'REVERSED', reversal_reason = ?, reversed_at = CURRENT_TIMESTAMP, reversed_by_user_id = ?, unallocated_amount = 0.0
           WHERE id = ?""",
        (reason, actor_user['id'], pay_dict['id'])
    )

    # 2. Deactivate all active allocations for this payment
    conn.execute(
        """UPDATE payment_allocations
           SET status = 'REVERSED', notes = notes || ' [REVERSED: ' || ? || ']'
           WHERE payment_id = ? AND status = 'ACTIVE'""",
        (reason, pay_dict['id'])
    )

    # 3. Log Audit Trail
    log_audit_event(
        conn,
        event_type="PAYMENT_REVERSED",
        order_id=pay_dict['order_id'] or "GENERAL",
        actor_user_id=actor_user['id'],
        actor_role=actor_user['role'],
        before_state={"status": "RECORDED", "amount": pay_dict['amount'], "reference_number": pay_dict['reference_number']},
        after_state={"status": "REVERSED", "reversal_reason": reason, "reversed_at": datetime.now().isoformat()},
        justification=reason,
        ip_address=ip_address
    )

    return get_payment_details(conn, pay_dict['id'], actor_user)


def get_payment_details(conn, payment_id_or_number, actor_user=None):
    """
    Retrieves complete payment details including counterparties and invoice allocations.
    Enforces role isolation.
    """
    pay = conn.execute(
        """SELECT p.*,
                  s.business_name as supplier_name, s.email as supplier_email,
                  n.business_name as nursery_name, n.email as nursery_email,
                  u.username as created_by_username
           FROM payments p
           JOIN users s ON p.supplier_user_id = s.id
           JOIN users n ON p.nursery_user_id = n.id
           LEFT JOIN users u ON p.created_by_user_id = u.id
           WHERE p.id = ? OR p.payment_number = ?""",
        (payment_id_or_number, payment_id_or_number)
    ).fetchone()

    if not pay:
        return None

    pay_dict = dict(pay)

    # Role Isolation Check
    if actor_user and actor_user.get('role') != 'ADMIN':
        user_id = actor_user.get('id')
        if user_id not in (pay_dict['supplier_user_id'], pay_dict['nursery_user_id']):
            raise PermissionError(f"Unauthorized: You do not have permission to view Payment #{pay_dict['payment_number']}.")

    # Fetch allocations
    allocations_rows = conn.execute(
        """SELECT a.*, i.invoice_number, i.total_amount as invoice_total, i.order_id
           FROM payment_allocations a
           JOIN invoices i ON a.invoice_id = i.id
           WHERE a.payment_id = ?
           ORDER BY a.allocated_at ASC, a.id ASC""",
        (pay_dict['id'],)
    ).fetchall()

    allocations = [dict(r) for r in allocations_rows]

    return {
        "payment": pay_dict,
        "allocations": allocations,
        "allocations_count": len(allocations),
        "supplier": {
            "id": pay_dict['supplier_user_id'],
            "name": pay_dict['supplier_name'],
            "email": pay_dict['supplier_email']
        },
        "nursery": {
            "id": pay_dict['nursery_user_id'],
            "name": pay_dict['nursery_name'],
            "email": pay_dict['nursery_email']
        }
    }


def list_payments_for_user(conn, actor_user, filters=None):
    """
    Lists payments accessible to the user, with support for search, method, status, and type filters.
    Enforces role isolation.
    Returns list of payments + aggregate KPI metrics.
    """
    if not actor_user:
        return {"payments": [], "kpi": {}}

    filters = filters or {}
    role = actor_user.get('role')
    user_id = actor_user.get('id')

    query = """
        SELECT p.*,
               s.business_name as supplier_name,
               n.business_name as nursery_name,
               i.invoice_number
        FROM payments p
        JOIN users s ON p.supplier_user_id = s.id
        JOIN users n ON p.nursery_user_id = n.id
        LEFT JOIN invoices i ON p.invoice_id = i.id
        WHERE 1=1
    """
    params = []

    if role == 'SUPPLIER':
        query += " AND p.supplier_user_id = ?"
        params.append(user_id)
    elif role == 'NURSERY':
        query += " AND p.nursery_user_id = ?"
        params.append(user_id)

    status_filter = filters.get('status')
    if status_filter and status_filter.upper() != 'ALL':
        query += " AND p.status = ?"
        params.append(status_filter.upper())

    method_filter = filters.get('payment_method')
    if method_filter and method_filter.upper() != 'ALL':
        query += " AND p.payment_method = ?"
        params.append(method_filter.upper())

    type_filter = filters.get('payment_type')
    if type_filter and type_filter.upper() != 'ALL':
        query += " AND p.payment_type = ?"
        params.append(type_filter.upper())

    invoice_id = filters.get('invoice_id')
    if invoice_id:
        query += " AND (p.invoice_id = ? OR p.id IN (SELECT payment_id FROM payment_allocations WHERE invoice_id = ?))"
        params.extend([invoice_id, invoice_id])

    order_id = filters.get('order_id')
    if order_id:
        query += " AND p.order_id = ?"
        params.append(order_id)

    search = filters.get('search', '').strip()
    if search:
        search_pattern = f"%{search}%"
        query += """ AND (
            p.payment_number LIKE ? OR
            p.reference_number LIKE ? OR
            p.notes LIKE ? OR
            s.business_name LIKE ? OR
            n.business_name LIKE ? OR
            i.invoice_number LIKE ?
        )"""
        params.extend([search_pattern] * 6)

    query += " ORDER BY p.payment_date DESC, p.created_at DESC"

    rows = conn.execute(query, params).fetchall()
    payments = [dict(r) for r in rows]

    # Calculate Global KPIs for this user's scope
    total_received = sum(p['amount'] for p in payments if p['status'] == 'RECORDED')
    total_unallocated_advances = sum(p['unallocated_amount'] for p in payments if p['status'] == 'RECORDED')

    # Query Invoices Outstanding for KPI
    inv_scope_query = "SELECT id, total_amount, status FROM invoices WHERE status != 'CANCELLED'"
    inv_params = []
    if role == 'SUPPLIER':
        inv_scope_query += " AND supplier_user_id = ?"
        inv_params.append(user_id)
    elif role == 'NURSERY':
        inv_scope_query += " AND nursery_user_id = ?"
        inv_params.append(user_id)

    invoices = conn.execute(inv_scope_query, inv_params).fetchall()
    total_invoiced = sum(i['total_amount'] for i in invoices)
    
    # Calculate total outstanding across active invoices
    settled_invoices_count = 0
    total_outstanding = Decimal('0.00')
    for inv_row in invoices:
        summary = get_invoice_payment_summary(conn, inv_row['id'])
        if summary:
            total_outstanding += quantize_currency(summary['outstanding_balance'])
            if summary['payment_status'] == 'PAID':
                settled_invoices_count += 1

    return {
        "payments": payments,
        "count": len(payments),
        "kpi": {
            "total_received": round(total_received, 2),
            "total_outstanding": float(total_outstanding),
            "total_unallocated_advances": round(total_unallocated_advances, 2),
            "settled_invoices_count": settled_invoices_count,
            "active_payments_count": len([p for p in payments if p['status'] == 'RECORDED'])
        }
    }


def get_order_payment_summary(conn, order_id, actor_user=None):
    """
    Summarizes all payments, advances, and invoice settlements for an order.
    """
    ord_row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not ord_row:
        return None

    ord_dict = dict(ord_row)
    if actor_user and actor_user.get('role') != 'ADMIN':
        user_id = actor_user.get('id')
        if user_id not in (ord_dict['supplier_user_id'], ord_dict['nursery_user_id']):
            raise PermissionError("Unauthorized to view payments for this order.")

    inv_rows = conn.execute("SELECT id, invoice_number, total_amount, status FROM invoices WHERE order_id = ?", (order_id,)).fetchall()
    invoices_summaries = []
    for i in inv_rows:
        sum_data = get_invoice_payment_summary(conn, i['id'])
        if sum_data:
            invoices_summaries.append(sum_data)

    pay_rows = conn.execute(
        """SELECT * FROM payments WHERE order_id = ? ORDER BY payment_date DESC, created_at DESC""",
        (order_id,)
    ).fetchall()
    payments = [dict(p) for p in pay_rows]

    total_order_invoiced = sum(s['total_amount'] for s in invoices_summaries)
    total_order_paid = sum(s['total_paid'] for s in invoices_summaries)
    total_order_outstanding = sum(s['outstanding_balance'] for s in invoices_summaries)

    return {
        "order_id": order_id,
        "invoices": invoices_summaries,
        "payments": payments,
        "total_invoiced": total_order_invoiced,
        "total_paid": total_order_paid,
        "total_outstanding": total_order_outstanding
    }

