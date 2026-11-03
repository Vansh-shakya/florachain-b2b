"""
FloraChain B2B — Phase 11: Ledger and Transaction History Service Layer
Financial Accuracy & Audit History Engine:
- Calculates balances strictly from authoritative database records (invoices, payments, allocations)
- Separates invoiced debt, allocated payments, unallocated advances, and outstanding principal
- Eliminates double-counting between payments and allocations
- Explicitly accounts for payment reversals and invoice cancellations without rewriting historical records
- Isolates accrued contractual late-payment interest from original invoice principal
- Employs Decimal / integer-paise arithmetic (ROUND_HALF_UP)
- Enforces strict role-based multi-tenant authorization
"""

import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from app.services.interest_service import calculate_invoice_interest


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


def parse_date_safe(date_val):
    """
    Parses a string or date into a datetime.date object.
    Returns None if parsing fails.
    """
    if not date_val:
        return None
    if isinstance(date_val, datetime):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    try:
        clean_str = str(date_val).split('T')[0].split(' ')[0].strip()
        return datetime.strptime(clean_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def get_ledger_summary(conn, actor_user, nursery_id=None):
    """
    Calculates the authoritative business balance summary for the authenticated user's relationship.
    
    Balance Formulas:
    1. Total Invoiced Gross = Sum(invoices.total_amount WHERE status = 'ISSUED')
    2. Total Payments Recorded = Sum(payments.amount WHERE status = 'RECORDED')
    3. Total Allocated Payments = Sum(payment_allocations.amount WHERE status = 'ACTIVE' AND payment.status = 'RECORDED' AND invoice.status = 'ISSUED')
    4. Total Unallocated Advances = Sum(payments.unallocated_amount WHERE status = 'RECORDED')
    5. Outstanding Principal = Total Invoiced Gross - Total Allocated Payments (max(0, ...))
    6. Net Balance Due = Total Invoiced Gross - Total Payments Recorded (= Outstanding Principal - Total Unallocated Advances)
    7. Accrued Late-Payment Interest = Sum(accrued_interest from calculate_invoice_interest() for all active issued invoices)
    8. Total Amount Payable (with Interest) = Outstanding Principal + Accrued Late-Payment Interest
    9. Total Payments Reversed = Sum(payments.amount WHERE status = 'REVERSED') (audit metric)
    
    Consistency Verification:
    Total Allocated Payments + Total Unallocated Advances MUST EQUAL Total Payments Recorded.
    """
    if not actor_user:
        raise PermissionError("Authentication required to view ledger summary.")

    role = actor_user.get('role')
    user_id = actor_user.get('id')

    # Base WHERE clauses for scoping
    inv_where = []
    inv_params = []
    pay_where = []
    pay_params = []
    alloc_where = []
    alloc_params = []

    if role == 'SUPPLIER':
        inv_where.append("i.supplier_user_id = ?")
        inv_params.append(user_id)
        pay_where.append("p.supplier_user_id = ?")
        pay_params.append(user_id)
        alloc_where.append("p.supplier_user_id = ?")
        alloc_params.append(user_id)
        if nursery_id:
            inv_where.append("i.nursery_user_id = ?")
            inv_params.append(nursery_id)
            pay_where.append("p.nursery_user_id = ?")
            pay_params.append(nursery_id)
            alloc_where.append("p.nursery_user_id = ?")
            alloc_params.append(nursery_id)
    elif role == 'NURSERY':
        inv_where.append("i.nursery_user_id = ?")
        inv_params.append(user_id)
        pay_where.append("p.nursery_user_id = ?")
        pay_params.append(user_id)
        alloc_where.append("p.nursery_user_id = ?")
        alloc_params.append(user_id)
    elif role == 'ADMIN':
        if nursery_id:
            inv_where.append("i.nursery_user_id = ?")
            inv_params.append(nursery_id)
            pay_where.append("p.nursery_user_id = ?")
            pay_params.append(nursery_id)
            alloc_where.append("p.nursery_user_id = ?")
            alloc_params.append(nursery_id)
    else:
        raise PermissionError("Unauthorized role.")

    # 1. Invoices Aggregation
    inv_clause = ("WHERE " + " AND ".join(inv_where)) if inv_where else ""
    inv_rows = conn.execute(f"""
        SELECT i.id, i.invoice_number, i.total_amount, i.status, i.due_date
        FROM invoices i
        {inv_clause}
    """, tuple(inv_params)).fetchall()

    total_invoiced_gross = Decimal('0.00')
    total_invoiced_cancelled = Decimal('0.00')
    active_invoices_count = 0
    cancelled_invoices_count = 0
    total_accrued_interest = Decimal('0.00')

    for row in inv_rows:
        amt = quantize_currency(row['total_amount'])
        if row['status'] == 'ISSUED':
            total_invoiced_gross += amt
            active_invoices_count += 1
            # Compute contractual accrued interest for this active invoice
            try:
                int_res = calculate_invoice_interest(conn, row['id'])
                if int_res and int_res.get('accrued_interest'):
                    total_accrued_interest += quantize_currency(int_res['accrued_interest'])
            except Exception:
                pass
        elif row['status'] == 'CANCELLED':
            total_invoiced_cancelled += amt
            cancelled_invoices_count += 1

    # 2. Payments Aggregation
    pay_clause = ("WHERE " + " AND ".join(pay_where)) if pay_where else ""
    pay_rows = conn.execute(f"""
        SELECT p.id, p.amount, p.unallocated_amount, p.status, p.payment_type
        FROM payments p
        {pay_clause}
    """, tuple(pay_params)).fetchall()

    total_payments_recorded = Decimal('0.00')
    total_payments_reversed = Decimal('0.00')
    total_unallocated_advances = Decimal('0.00')
    recorded_payments_count = 0
    reversed_payments_count = 0

    for row in pay_rows:
        amt = quantize_currency(row['amount'])
        unalloc = quantize_currency(row['unallocated_amount'])
        if row['status'] == 'RECORDED':
            total_payments_recorded += amt
            total_unallocated_advances += unalloc
            recorded_payments_count += 1
        elif row['status'] == 'REVERSED':
            total_payments_reversed += amt
            reversed_payments_count += 1

    # 3. Active Allocations Aggregation
    alloc_clause = ("WHERE " + " AND ".join(alloc_where + ["a.status = 'ACTIVE'", "p.status = 'RECORDED'", "i.status = 'ISSUED'"]))
    alloc_rows = conn.execute(f"""
        SELECT a.amount
        FROM payment_allocations a
        JOIN payments p ON a.payment_id = p.id
        JOIN invoices i ON a.invoice_id = i.id
        {alloc_clause}
    """, tuple(alloc_params)).fetchall()

    total_allocated_payments = Decimal('0.00')
    for row in alloc_rows:
        total_allocated_payments += quantize_currency(row['amount'])

    # 4. Balances Calculation
    outstanding_principal = max(Decimal('0.00'), total_invoiced_gross - total_allocated_payments)
    net_balance_due = total_invoiced_gross - total_payments_recorded
    total_amount_payable_with_interest = outstanding_principal + total_accrued_interest

    # 5. Internal Consistency Check
    cash_allocated_and_unallocated = total_allocated_payments + total_unallocated_advances
    variance = cash_allocated_and_unallocated - total_payments_recorded
    is_balanced = (abs(variance) == Decimal('0.00'))

    return {
        "total_invoiced_gross": float(total_invoiced_gross),
        "total_invoiced_cancelled": float(total_invoiced_cancelled),
        "active_invoices_count": active_invoices_count,
        "cancelled_invoices_count": cancelled_invoices_count,
        "total_payments_recorded": float(total_payments_recorded),
        "total_payments_reversed": float(total_payments_reversed),
        "recorded_payments_count": recorded_payments_count,
        "reversed_payments_count": reversed_payments_count,
        "total_allocated_payments": float(total_allocated_payments),
        "total_unallocated_advances": float(total_unallocated_advances),
        "outstanding_principal": float(outstanding_principal),
        "net_balance_due": float(net_balance_due),
        "total_accrued_interest": float(total_accrued_interest),
        "total_amount_payable_with_interest": float(total_amount_payable_with_interest),
        "is_balanced": is_balanced,
        "balance_variance": float(variance),
        "consistency_check": {
            "is_balanced": is_balanced,
            "cash_allocated_plus_unallocated": float(cash_allocated_and_unallocated),
            "total_active_payments": float(total_payments_recorded),
            "variance": float(variance)
        }
    }


def get_ledger_entries(conn, actor_user, filters=None):
    """
    Retrieves chronological, unified ledger transactions belonging to the authenticated user's relationship.
    
    Supports filters:
    - nursery_id: filter by specific nursery client
    - type: filter by transaction type
    - start_date: filter by transaction_date >= start_date (YYYY-MM-DD)
    - end_date: filter by transaction_date <= end_date (YYYY-MM-DD)
    - search: search text matching references, notes, order, invoice, parties
    - status: 'ALL', 'ACTIVE', 'REVERSED', 'CANCELLED'
    - order: 'desc' (default: newest first) or 'asc' (chronological forward)
    """
    if not actor_user:
        raise PermissionError("Authentication required to view ledger transaction history.")

    role = actor_user.get('role')
    user_id = actor_user.get('id')
    filters = filters or {}
    nursery_id = filters.get('nursery_id')

    # Validate nursery_id filter
    if nursery_id is not None and str(nursery_id).strip() != '' and str(nursery_id).upper() != 'ALL':
        try:
            nursery_id = int(nursery_id)
        except ValueError:
            nursery_id = None
    else:
        nursery_id = None

    entries = []

    # -------------------------------------------------------------------------
    # 1. Collect Invoices (Issuance & Cancellation)
    # -------------------------------------------------------------------------
    inv_where = []
    inv_params = []

    if role == 'SUPPLIER':
        inv_where.append("i.supplier_user_id = ?")
        inv_params.append(user_id)
        if nursery_id:
            inv_where.append("i.nursery_user_id = ?")
            inv_params.append(nursery_id)
    elif role == 'NURSERY':
        inv_where.append("i.nursery_user_id = ?")
        inv_params.append(user_id)
    elif role == 'ADMIN':
        if nursery_id:
            inv_where.append("i.nursery_user_id = ?")
            inv_params.append(nursery_id)

    inv_clause = ("WHERE " + " AND ".join(inv_where)) if inv_where else ""
    inv_query = f"""
        SELECT i.*,
               s.business_name as supplier_name, s.email as supplier_email,
               n.business_name as nursery_name, n.email as nursery_email
        FROM invoices i
        JOIN users s ON i.supplier_user_id = s.id
        JOIN users n ON i.nursery_user_id = n.id
        {inv_clause}
    """
    for r in conn.execute(inv_query, tuple(inv_params)).fetchall():
        inv_dict = dict(r)
        inv_date = inv_dict.get('invoice_date') or (inv_dict.get('created_at', '').split(' ')[0] if inv_dict.get('created_at') else '')
        amount_val = float(quantize_currency(inv_dict['total_amount']))

        # INVOICE_ISSUED entry
        entries.append({
            "id": f"TX-INV-{inv_dict['invoice_number']}",
            "transaction_date": inv_date,
            "timestamp": inv_dict.get('created_at') or f"{inv_date} 09:00:00",
            "transaction_type": "INVOICE_ISSUED",
            "type": "INVOICE_ISSUED",
            "reference_number": inv_dict['invoice_number'],
            "reference_id": inv_dict['invoice_number'],
            "external_reference": inv_dict.get('agreement_ref') or "",
            "related_reference": inv_dict.get('agreement_ref') or inv_dict.get('order_id') or "",
            "order_id": inv_dict['order_id'],
            "invoice_id": inv_dict['id'],
            "payment_id": None,
            "supplier_id": inv_dict['supplier_user_id'],
            "supplier_name": inv_dict['supplier_name'],
            "nursery_id": inv_dict['nursery_user_id'],
            "nursery_name": inv_dict['nursery_name'],
            "entry_direction": "DEBIT",
            "direction": "DEBIT",
            "amount": amount_val,
            "currency": inv_dict.get('currency', 'INR'),
            "status": inv_dict['status'],
            "is_reversed_or_cancelled": inv_dict['status'] == 'CANCELLED',
            "description": f"Commercial wholesale invoice #{inv_dict['invoice_number']} issued for Order #{inv_dict['order_id']} ({inv_dict.get('total_quantity', 0)} units).",
            "precedence": 2,
            "metadata": {
                "due_date": inv_dict.get('due_date'),
                "subtotal": float(quantize_currency(inv_dict.get('subtotal'))),
                "tax_amount": float(quantize_currency(inv_dict.get('tax_amount'))),
                "discount_amount": float(quantize_currency(inv_dict.get('discount_amount'))),
                "damage_billing_policy": inv_dict.get('damage_billing_policy'),
                "notes": inv_dict.get('notes', '')
            }
        })

        # If cancelled, add INVOICE_CANCELLED entry
        if inv_dict['status'] == 'CANCELLED':
            entries.append({
                "id": f"TX-CANCEL-{inv_dict['invoice_number']}",
                "transaction_date": inv_date,
                "timestamp": inv_dict.get('created_at') or f"{inv_date} 23:59:59",
                "transaction_type": "INVOICE_CANCELLED",
                "type": "INVOICE_CANCELLED",
                "reference_number": f"CANCEL-{inv_dict['invoice_number']}",
                "reference_id": f"CANCEL-{inv_dict['invoice_number']}",
                "external_reference": inv_dict['invoice_number'],
                "related_reference": inv_dict['invoice_number'],
                "order_id": inv_dict['order_id'],
                "invoice_id": inv_dict['id'],
                "payment_id": None,
                "supplier_id": inv_dict['supplier_user_id'],
                "supplier_name": inv_dict['supplier_name'],
                "nursery_id": inv_dict['nursery_user_id'],
                "nursery_name": inv_dict['nursery_name'],
                "entry_direction": "ADJUSTMENT",
                "direction": "ADJUSTMENT",
                "amount": amount_val,
                "currency": inv_dict.get('currency', 'INR'),
                "status": "CANCELLED",
                "is_reversed_or_cancelled": True,
                "description": f"Invoice #{inv_dict['invoice_number']} cancelled. Nullified debt obligation.",
                "precedence": 7,
                "metadata": {
                    "original_invoice_number": inv_dict['invoice_number']
                }
            })

    # -------------------------------------------------------------------------
    # 2. Collect Payments (Receipts, Advances & Reversals)
    # -------------------------------------------------------------------------
    pay_where = []
    pay_params = []

    if role == 'SUPPLIER':
        pay_where.append("p.supplier_user_id = ?")
        pay_params.append(user_id)
        if nursery_id:
            pay_where.append("p.nursery_user_id = ?")
            pay_params.append(nursery_id)
    elif role == 'NURSERY':
        pay_where.append("p.nursery_user_id = ?")
        pay_params.append(user_id)
    elif role == 'ADMIN':
        if nursery_id:
            pay_where.append("p.nursery_user_id = ?")
            pay_params.append(nursery_id)

    pay_clause = ("WHERE " + " AND ".join(pay_where)) if pay_where else ""
    pay_query = f"""
        SELECT p.*,
               s.business_name as supplier_name, s.email as supplier_email,
               n.business_name as nursery_name, n.email as nursery_email,
               i.invoice_number as linked_invoice_number
        FROM payments p
        JOIN users s ON p.supplier_user_id = s.id
        JOIN users n ON p.nursery_user_id = n.id
        LEFT JOIN invoices i ON p.invoice_id = i.id
        {pay_clause}
    """
    for r in conn.execute(pay_query, tuple(pay_params)).fetchall():
        pay_dict = dict(r)
        pay_date = pay_dict.get('payment_date') or (pay_dict.get('created_at', '').split(' ')[0] if pay_dict.get('created_at') else '')
        amount_val = float(quantize_currency(pay_dict['amount']))
        is_advance = pay_dict.get('payment_type') == 'ADVANCE_PAYMENT'
        tx_type = "ADVANCE_RECORDED" if is_advance else "PAYMENT_RECORDED"

        # Active or recorded payment entry
        entries.append({
            "id": f"TX-PAY-{pay_dict['payment_number']}",
            "transaction_date": pay_date,
            "timestamp": pay_dict.get('created_at') or f"{pay_date} 10:00:00",
            "transaction_type": tx_type,
            "type": tx_type,
            "reference_number": pay_dict['payment_number'],
            "reference_id": pay_dict['payment_number'],
            "external_reference": pay_dict.get('reference_number') or "",
            "related_reference": pay_dict.get('reference_number') or pay_dict.get('linked_invoice_number') or "",
            "order_id": pay_dict.get('order_id'),
            "invoice_id": pay_dict.get('invoice_id'),
            "payment_id": pay_dict['id'],
            "supplier_id": pay_dict['supplier_user_id'],
            "supplier_name": pay_dict['supplier_name'],
            "nursery_id": pay_dict['nursery_user_id'],
            "nursery_name": pay_dict['nursery_name'],
            "entry_direction": "CREDIT",
            "direction": "CREDIT",
            "amount": amount_val,
            "currency": "INR",
            "status": pay_dict['status'],
            "is_reversed_or_cancelled": pay_dict['status'] == 'REVERSED',
            "description": f"{'Advance deposit' if is_advance else 'Payment receipt'} #{pay_dict['payment_number']} recorded via {pay_dict['payment_method']} (Ref: {pay_dict.get('reference_number', 'N/A')}).",
            "precedence": 3,
            "metadata": {
                "payment_method": pay_dict['payment_method'],
                "unallocated_amount": float(quantize_currency(pay_dict.get('unallocated_amount'))),
                "notes": pay_dict.get('notes', '')
            }
        })

        # If reversed, add PAYMENT_REVERSED entry
        if pay_dict['status'] == 'REVERSED':
            rev_date = pay_dict.get('reversed_at', '').split(' ')[0] if pay_dict.get('reversed_at') else pay_date
            entries.append({
                "id": f"TX-REV-{pay_dict['payment_number']}",
                "transaction_date": rev_date,
                "timestamp": pay_dict.get('reversed_at') or f"{rev_date} 12:00:00",
                "transaction_type": "PAYMENT_REVERSED",
                "type": "PAYMENT_REVERSED",
                "reference_number": f"REV-{pay_dict['payment_number']}",
                "reference_id": f"REV-{pay_dict['payment_number']}",
                "external_reference": pay_dict['payment_number'],
                "related_reference": pay_dict['payment_number'],
                "order_id": pay_dict.get('order_id'),
                "invoice_id": pay_dict.get('invoice_id'),
                "payment_id": pay_dict['id'],
                "supplier_id": pay_dict['supplier_user_id'],
                "supplier_name": pay_dict['supplier_name'],
                "nursery_id": pay_dict['nursery_user_id'],
                "nursery_name": pay_dict['nursery_name'],
                "entry_direction": "REVERSAL",
                "direction": "REVERSAL",
                "amount": amount_val,
                "currency": "INR",
                "status": "REVERSED",
                "is_reversed_or_cancelled": True,
                "description": f"Payment #{pay_dict['payment_number']} reversed. Reason: {pay_dict.get('reversal_reason') or 'Administrative correction'}.",
                "precedence": 6,
                "metadata": {
                    "reversal_reason": pay_dict.get('reversal_reason'),
                    "original_payment_number": pay_dict['payment_number']
                }
            })

    # -------------------------------------------------------------------------
    # 3. Collect Payment Allocations (Settlement Transfers)
    # -------------------------------------------------------------------------
    alloc_where = []
    alloc_params = []

    if role == 'SUPPLIER':
        alloc_where.append("p.supplier_user_id = ?")
        alloc_params.append(user_id)
        if nursery_id:
            alloc_where.append("p.nursery_user_id = ?")
            alloc_params.append(nursery_id)
    elif role == 'NURSERY':
        alloc_where.append("p.nursery_user_id = ?")
        alloc_params.append(user_id)
    elif role == 'ADMIN':
        if nursery_id:
            alloc_where.append("p.nursery_user_id = ?")
            alloc_params.append(nursery_id)

    alloc_clause = ("WHERE " + " AND ".join(alloc_where)) if alloc_where else ""
    alloc_query = f"""
        SELECT a.*,
               p.payment_number, p.payment_date, p.payment_type, p.supplier_user_id, p.nursery_user_id,
               s.business_name as supplier_name,
               n.business_name as nursery_name,
               i.invoice_number, i.order_id
        FROM payment_allocations a
        JOIN payments p ON a.payment_id = p.id
        JOIN invoices i ON a.invoice_id = i.id
        JOIN users s ON p.supplier_user_id = s.id
        JOIN users n ON p.nursery_user_id = n.id
        {alloc_clause}
    """
    for r in conn.execute(alloc_query, tuple(alloc_params)).fetchall():
        alloc_dict = dict(r)
        alloc_date = alloc_dict.get('allocated_at', '').split(' ')[0] if alloc_dict.get('allocated_at') else alloc_dict.get('payment_date', '')
        alloc_amt = float(quantize_currency(alloc_dict['amount']))
        is_adv = alloc_dict.get('payment_type') == 'ADVANCE_PAYMENT'
        tx_type = "ADVANCE_ALLOCATED" if is_adv else "PAYMENT_ALLOCATED"

        entries.append({
            "id": f"TX-ALLOC-{alloc_dict['id']}",
            "transaction_date": alloc_date,
            "timestamp": alloc_dict.get('allocated_at') or f"{alloc_date} 11:00:00",
            "transaction_type": tx_type,
            "type": tx_type,
            "reference_number": f"ALLOC-{alloc_dict['payment_number']}-{alloc_dict['id']}",
            "reference_id": f"ALLOC-{alloc_dict['payment_number']}-{alloc_dict['id']}",
            "external_reference": alloc_dict['payment_number'],
            "related_reference": alloc_dict['invoice_number'],
            "order_id": alloc_dict.get('order_id'),
            "invoice_id": alloc_dict.get('invoice_id'),
            "payment_id": alloc_dict.get('payment_id'),
            "supplier_id": alloc_dict['supplier_user_id'],
            "supplier_name": alloc_dict['supplier_name'],
            "nursery_id": alloc_dict['nursery_user_id'],
            "nursery_name": alloc_dict['nursery_name'],
            "entry_direction": "SETTLEMENT",
            "direction": "SETTLEMENT",
            "amount": alloc_amt,
            "currency": "INR",
            "status": alloc_dict['status'],
            "is_reversed_or_cancelled": alloc_dict['status'] == 'REVERSED',
            "description": f"Allocation of ₹{alloc_amt:,.2f} from {alloc_dict['payment_number']} to Invoice #{alloc_dict['invoice_number']}.",
            "precedence": 4,
            "metadata": {
                "source_payment_number": alloc_dict['payment_number'],
                "target_invoice_number": alloc_dict['invoice_number'],
                "notes": alloc_dict.get('notes', '')
            }
        })

    # -------------------------------------------------------------------------
    # 4. Collect Invoice Terms Amendments (from audit_events)
    # -------------------------------------------------------------------------
    terms_query = """
        SELECT a.id, a.order_id, a.created_at, a.before_state_json, a.after_state_json, a.justification,
               o.supplier_user_id, o.nursery_user_id,
               s.business_name as supplier_name,
               n.business_name as nursery_name
        FROM audit_events a
        JOIN orders o ON a.order_id = o.id
        JOIN users s ON o.supplier_user_id = s.id
        JOIN users n ON o.nursery_user_id = n.id
        WHERE a.event_type = 'INVOICE_TERMS_UPDATED'
    """
    terms_params = []
    if role == 'SUPPLIER':
        terms_query += " AND o.supplier_user_id = ?"
        terms_params.append(user_id)
        if nursery_id:
            terms_query += " AND o.nursery_user_id = ?"
            terms_params.append(nursery_id)
    elif role == 'NURSERY':
        terms_query += " AND o.nursery_user_id = ?"
        terms_params.append(user_id)
    elif role == 'ADMIN':
        if nursery_id:
            terms_query += " AND o.nursery_user_id = ?"
            terms_params.append(nursery_id)

    for r in conn.execute(terms_query, tuple(terms_params)).fetchall():
        row_dict = dict(r)
        evt_date = row_dict['created_at'].split(' ')[0] if row_dict.get('created_at') else ''
        after_state = json.loads(row_dict.get('after_state_json') or '{}')
        entries.append({
            "id": f"TX-AUD-{row_dict['id']}",
            "transaction_date": evt_date,
            "timestamp": row_dict['created_at'],
            "transaction_type": "TERMS_AMENDED",
            "type": "TERMS_AMENDED",
            "reference_number": f"AUD-TERMS-{row_dict['id']}",
            "reference_id": f"AUD-TERMS-{row_dict['id']}",
            "external_reference": row_dict['order_id'],
            "related_reference": row_dict['order_id'],
            "order_id": row_dict['order_id'],
            "invoice_id": None,
            "payment_id": None,
            "supplier_id": row_dict['supplier_user_id'],
            "supplier_name": row_dict['supplier_name'],
            "nursery_id": row_dict['nursery_user_id'],
            "nursery_name": row_dict['nursery_name'],
            "entry_direction": "AUDIT",
            "direction": "AUDIT",
            "amount": None,
            "currency": "INR",
            "status": "AMENDED",
            "is_reversed_or_cancelled": False,
            "description": f"Contractual payment terms amended for Order #{row_dict['order_id']}: Due date {after_state.get('due_date', 'N/A')}, Rate {after_state.get('interest_rate_pct', 0)}% p.a. {row_dict.get('justification', '')}",
            "precedence": 5,
            "metadata": {
                "after_state": after_state,
                "justification": row_dict.get('justification', '')
            }
        })

    # -------------------------------------------------------------------------
    # 5. Collect Delivery Verifications (from delivery_inspections)
    # -------------------------------------------------------------------------
    verif_query = """
        SELECT d.id, d.order_id, d.sound_qty, d.damaged_qty, d.delivered_qty, d.locked_at,
               o.supplier_user_id, o.nursery_user_id,
               s.business_name as supplier_name,
               n.business_name as nursery_name
        FROM delivery_inspections d
        JOIN orders o ON d.order_id = o.id
        JOIN users s ON o.supplier_user_id = s.id
        JOIN users n ON o.nursery_user_id = n.id
        WHERE d.is_locked = 1
    """
    verif_params = []
    if role == 'SUPPLIER':
        verif_query += " AND o.supplier_user_id = ?"
        verif_params.append(user_id)
        if nursery_id:
            verif_query += " AND o.nursery_user_id = ?"
            verif_params.append(nursery_id)
    elif role == 'NURSERY':
        verif_query += " AND o.nursery_user_id = ?"
        verif_params.append(user_id)
    elif role == 'ADMIN':
        if nursery_id:
            verif_query += " AND o.nursery_user_id = ?"
            verif_params.append(nursery_id)

    for r in conn.execute(verif_query, tuple(verif_params)).fetchall():
        row_dict = dict(r)
        verif_date = row_dict['locked_at'].split(' ')[0] if row_dict.get('locked_at') else ''
        entries.append({
            "id": f"TX-VERIF-{row_dict['order_id']}",
            "transaction_date": verif_date,
            "timestamp": row_dict['locked_at'] or f"{verif_date} 08:00:00",
            "transaction_type": "DELIVERY_VERIFIED",
            "type": "DELIVERY_VERIFIED",
            "reference_number": f"VERIF-{row_dict['order_id']}",
            "reference_id": f"VERIF-{row_dict['order_id']}",
            "external_reference": row_dict['order_id'],
            "related_reference": row_dict['order_id'],
            "order_id": row_dict['order_id'],
            "invoice_id": None,
            "payment_id": None,
            "supplier_id": row_dict['supplier_user_id'],
            "supplier_name": row_dict['supplier_name'],
            "nursery_id": row_dict['nursery_user_id'],
            "nursery_name": row_dict['nursery_name'],
            "entry_direction": "VERIFICATION",
            "direction": "VERIFICATION",
            "amount": None,
            "currency": "INR",
            "status": "VERIFIED",
            "is_reversed_or_cancelled": False,
            "description": f"Physical delivery verified and dual counter-signed for Order #{row_dict['order_id']} ({row_dict.get('sound_qty', 0)} sound plants).",
            "precedence": 1,
            "metadata": {
                "sound_qty": row_dict.get('sound_qty'),
                "damaged_qty": row_dict.get('damaged_qty'),
                "delivered_qty": row_dict.get('delivered_qty')
            }
        })

    # -------------------------------------------------------------------------
    # 6. Filtering
    # -------------------------------------------------------------------------
    filtered = entries

    # Filter by transaction_type
    type_filter = (filters.get('type') or filters.get('transaction_type') or 'ALL').strip().upper()
    if type_filter and type_filter != 'ALL':
        filtered = [e for e in filtered if e['transaction_type'] == type_filter or type_filter in e['transaction_type']]

    # Filter by start_date
    start_date = parse_date_safe(filters.get('start_date'))
    if start_date:
        filtered = [e for e in filtered if parse_date_safe(e['transaction_date']) and parse_date_safe(e['transaction_date']) >= start_date]

    # Filter by end_date
    end_date = parse_date_safe(filters.get('end_date'))
    if end_date:
        filtered = [e for e in filtered if parse_date_safe(e['transaction_date']) and parse_date_safe(e['transaction_date']) <= end_date]

    # Filter by status
    status_filter = (filters.get('status') or 'ALL').strip().upper()
    if status_filter and status_filter != 'ALL':
        if status_filter == 'ACTIVE':
            filtered = [e for e in filtered if not e['is_reversed_or_cancelled']]
        elif status_filter in ('REVERSED', 'CANCELLED'):
            filtered = [e for e in filtered if e['status'] == status_filter]
        else:
            filtered = [e for e in filtered if e['status'].upper() == status_filter]

    # Filter by search keyword
    search_q = (filters.get('search') or filters.get('q') or '').strip().lower()
    if search_q:
        filtered = [
            e for e in filtered
            if search_q in e['reference_number'].lower()
            or (e['external_reference'] and search_q in e['external_reference'].lower())
            or (e['order_id'] and search_q in e['order_id'].lower())
            or (e['invoice_id'] and search_q in str(e['invoice_id']).lower())
            or search_q in e['description'].lower()
            or search_q in e['nursery_name'].lower()
            or search_q in e['supplier_name'].lower()
        ]

    # -------------------------------------------------------------------------
    # 7. Deterministic Sorting
    # -------------------------------------------------------------------------
    is_asc = (filters.get('order') or 'desc').strip().lower() == 'asc'
    
    def sort_key(entry):
        # 1. Commercial transaction date (YYYY-MM-DD)
        dt_val = entry['transaction_date'] or ''
        # 2. Type precedence (earlier in workflow comes first on same date)
        prec = entry.get('precedence', 99)
        # 3. Exact timestamp
        ts = entry.get('timestamp') or ''
        # 4. ID tie-break
        eid = entry['id']
        return (dt_val, prec, ts, eid)

    filtered.sort(key=sort_key, reverse=not is_asc)

    # -------------------------------------------------------------------------
    # 8. Counterparties available for filter dropdown
    # -------------------------------------------------------------------------
    counterparties_set = {}
    for e in entries:
        nid = e.get('nursery_id')
        nname = e.get('nursery_name')
        if nid and nname and nid not in counterparties_set:
            counterparties_set[nid] = nname

    counterparties = [{"id": k, "name": v} for k, v in sorted(counterparties_set.items(), key=lambda x: x[1])]

    # Calculate authoritative balance summary
    summary = get_ledger_summary(conn, actor_user, nursery_id)

    return {
        "entries": filtered,
        "count": len(filtered),
        "total_records_unfiltered": len(entries),
        "summary": summary,
        "counterparties": counterparties
    }
