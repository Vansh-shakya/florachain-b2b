"""
FloraChain B2B — Due Date & Agreed Late-Payment Interest Calculation Engine
Phase 10: Contractual Due Date Tracking, Stepwise Overdue Interest & Auditability

Core Rules & Financial Integrity:
- Interest is calculated strictly on the eligible overdue outstanding principal based on agreed contract terms.
- No default interest rate is ever invented. If no valid agreement exists or rate is 0%, interest is strictly ₹0.00.
- Calculations account for all partial payments, payment allocations, and reversals.
  Interest ceases to accrue on amounts from the exact date they are settled.
- Standard B2B Commercial Convention:
  * Basis: ANNUAL_SIMPLE (Actual/365 simple interest)
  * Formula: Overdue Principal * (Agreed Annual Rate / 100) * (Days Overdue / 365)
  * Rounded to 2 decimal places using Decimal / ROUND_HALF_UP (paise precision)
- Accrued interest is kept completely distinct from the original frozen invoice principal.
  Issued invoice amounts are never altered.
- Reversible and auditable: Breakdown of calculation segments is transparently generated.
"""

import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta
from app.services.audit_service import log_audit_event


VALID_BASES = ('ANNUAL_SIMPLE', 'MONTHLY_SIMPLE', 'DAILY_SIMPLE', 'NONE')


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


def calculate_invoice_interest(conn, invoice_id_or_number, as_of_date=None):
    """
    Calculates contractual late-payment interest on an issued invoice:
    - Checks agreed due date and interest rate from frozen terms or invoice record
    - Excludes settled amounts from accrual after their settlement date
    - Employs stepwise timeline calculation across partial payment dates
    - Returns due status, overdue days, accrued interest, and audit breakdown
    """
    inv = conn.execute(
        """SELECT * FROM invoices WHERE id = ? OR invoice_number = ?""",
        (invoice_id_or_number, invoice_id_or_number)
    ).fetchone()

    if not inv:
        return None

    inv_dict = dict(inv)
    invoice_total = quantize_currency(inv_dict['total_amount'])

    # Determine evaluation date
    eval_date = parse_date_safe(as_of_date) or date.today()
    due_date = parse_date_safe(inv_dict.get('due_date'))
    invoice_date = parse_date_safe(inv_dict.get('invoice_date')) or due_date or eval_date

    # Contractual Interest Terms
    raw_rate = inv_dict.get('interest_rate_pct')
    rate_pct = quantize_currency(raw_rate if raw_rate is not None else 0.0)
    basis = str(inv_dict.get('interest_calculation_basis') or 'ANNUAL_SIMPLE').upper().strip()
    if basis not in VALID_BASES:
        basis = 'ANNUAL_SIMPLE'
    grace_period_days = max(0, int(inv_dict.get('interest_grace_period_days') or 0))

    # Fetch active payment allocations ordered by payment date
    alloc_rows = conn.execute(
        """SELECT a.*, p.payment_date, p.payment_number, p.reference_number
           FROM payment_allocations a
           JOIN payments p ON a.payment_id = p.id
           WHERE a.invoice_id = ? AND a.status = 'ACTIVE' AND p.status = 'RECORDED'
           ORDER BY p.payment_date ASC, a.id ASC""",
        (inv_dict['id'],)
    ).fetchall()

    allocations = []
    total_paid = Decimal('0.00')
    for r in alloc_rows:
        amt = quantize_currency(r['amount'])
        pdate = parse_date_safe(r['payment_date']) or invoice_date
        total_paid += amt
        allocations.append({
            "payment_id": r['payment_id'],
            "payment_number": r['payment_number'],
            "reference_number": r['reference_number'],
            "amount": amt,
            "payment_date": pdate
        })

    current_outstanding_principal = max(Decimal('0.00'), invoice_total - total_paid)

    # 1. Evaluate Due Date Status
    if inv_dict.get('status') == 'CANCELLED':
        due_status = 'CANCELLED'
        overdue_days = 0
    elif current_outstanding_principal == Decimal('0.00'):
        due_status = 'SETTLED'
        overdue_days = 0
    elif not due_date:
        due_status = 'NO_DUE_DATE'
        overdue_days = 0
    elif eval_date <= due_date:
        due_status = 'NOT_DUE'
        overdue_days = 0
    else:
        raw_overdue_days = (eval_date - due_date).days
        if raw_overdue_days <= grace_period_days:
            due_status = 'IN_GRACE_PERIOD'
            overdue_days = 0
        else:
            due_status = 'OVERDUE'
            overdue_days = raw_overdue_days

    # 2. Check Interest Applicability
    is_applicable = (
        due_status == 'OVERDUE' and
        rate_pct > Decimal('0.00') and
        basis != 'NONE' and
        due_date is not None
    )

    if not is_applicable:
        return {
            "invoice_id": inv_dict['id'],
            "invoice_number": inv_dict['invoice_number'],
            "order_id": inv_dict['order_id'],
            "invoice_date": invoice_date.isoformat() if invoice_date else None,
            "due_date": due_date.isoformat() if due_date else None,
            "as_of_date": eval_date.isoformat(),
            "due_status": due_status,
            "overdue_days": overdue_days,
            "is_interest_applicable": False,
            "interest_rate_pct": float(rate_pct),
            "interest_calculation_basis": basis,
            "interest_grace_period_days": grace_period_days,
            "invoice_total": float(invoice_total),
            "original_principal": float(invoice_total),
            "total_paid": float(total_paid),
            "outstanding_principal": float(current_outstanding_principal),
            "accrued_interest": 0.00,
            "total_amount_payable": float(current_outstanding_principal),
            "calculation_breakdown": []
        }

    # 3. Stepwise Timeline Interest Calculation
    # Overdue interest accrues from due_date onwards on the unpaid principal balance.
    interest_start_date = due_date
    if grace_period_days > 0:
        interest_start_date = due_date + timedelta(days=grace_period_days)

    # Initial principal as of interest_start_date:
    # Deduct allocations made on or prior to interest_start_date
    prior_settled = sum(a['amount'] for a in allocations if a['payment_date'] <= interest_start_date)
    initial_overdue_principal = max(Decimal('0.00'), invoice_total - prior_settled)

    # Gather timeline checkpoint dates strictly between interest_start_date and eval_date
    checkpoint_dates = {interest_start_date, eval_date}
    for a in allocations:
        if interest_start_date < a['payment_date'] < eval_date:
            checkpoint_dates.add(a['payment_date'])

    sorted_dates = sorted(list(checkpoint_dates))

    breakdown = []
    total_accrued = Decimal('0.00')
    running_principal = initial_overdue_principal

    for i in range(len(sorted_dates) - 1):
        period_start = sorted_dates[i]
        period_end = sorted_dates[i + 1]
        days_in_period = (period_end - period_start).days

        if days_in_period > 0 and running_principal > Decimal('0.00'):
            # Calculate interest for this specific interval
            if basis == 'ANNUAL_SIMPLE':
                # Actual/365 Simple Interest
                period_interest = running_principal * (rate_pct / Decimal('100')) * (Decimal(days_in_period) / Decimal('365'))
            elif basis == 'MONTHLY_SIMPLE':
                # 30/360 or Monthly rate
                period_interest = running_principal * (rate_pct / Decimal('100')) * (Decimal(days_in_period) / Decimal('360'))
            elif basis == 'DAILY_SIMPLE':
                period_interest = running_principal * (rate_pct / Decimal('100')) * Decimal(days_in_period)
            else:
                period_interest = Decimal('0.00')

            period_interest_quant = quantize_currency(period_interest)
            total_accrued += period_interest_quant

            breakdown.append({
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "days": days_in_period,
                "eligible_principal": float(running_principal),
                "principal": float(running_principal),
                "annual_rate_pct": float(rate_pct),
                "rate_pct": float(rate_pct),
                "accrued_amount": float(period_interest_quant),
                "interest": float(period_interest_quant)
            })

        # Apply allocations that occurred at period_end to reduce running principal for next interval
        settled_at_end = sum(a['amount'] for a in allocations if a['payment_date'] == period_end)
        running_principal = max(Decimal('0.00'), running_principal - settled_at_end)

    total_amount_payable = quantize_currency(current_outstanding_principal + total_accrued)

    return {
        "invoice_id": inv_dict['id'],
        "invoice_number": inv_dict['invoice_number'],
        "order_id": inv_dict['order_id'],
        "invoice_date": invoice_date.isoformat() if invoice_date else None,
        "due_date": due_date.isoformat() if due_date else None,
        "as_of_date": eval_date.isoformat(),
        "due_status": due_status,
        "overdue_days": overdue_days,
        "is_interest_applicable": True,
        "interest_rate_pct": float(rate_pct),
        "interest_calculation_basis": basis,
        "interest_grace_period_days": grace_period_days,
        "invoice_total": float(invoice_total),
        "original_principal": float(invoice_total),
        "total_paid": float(total_paid),
        "outstanding_principal": float(current_outstanding_principal),
        "accrued_interest": float(total_accrued),
        "total_amount_payable": float(total_amount_payable),
        "calculation_breakdown": breakdown
    }


def record_invoice_agreed_terms(conn, invoice_id_or_number, terms_data, actor_user, ip_address="127.0.0.1"):
    """
    Records or updates agreed due date and interest parameters on an issued invoice:
    - Validates inputs (rate >= 0, basis in VALID_BASES, grace_days >= 0)
    - Enforces authorization (Supplier or Admin)
    - Updates invoice and logs audit event
    """
    if not actor_user or actor_user.get('role') not in ('SUPPLIER', 'ADMIN'):
        raise PermissionError("Only wholesale suppliers or platform administrators can update invoice payment terms.")

    inv = conn.execute(
        "SELECT * FROM invoices WHERE id = ? OR invoice_number = ?",
        (invoice_id_or_number, invoice_id_or_number)
    ).fetchone()
    if not inv:
        raise ValueError(f"Invoice '{invoice_id_or_number}' not found.")
    inv_dict = dict(inv)

    if inv_dict['status'] == 'CANCELLED':
        raise ValueError("Cannot modify terms on a cancelled invoice.")

    if actor_user.get('role') == 'SUPPLIER' and actor_user.get('id') != inv_dict['supplier_user_id']:
        raise PermissionError("Unauthorized: You can only update terms on invoices belonging to your business.")

    # Validate inputs
    if 'due_date' in terms_data:
        due_date_str = str(terms_data.get('due_date') or '').strip()
        if not due_date_str:
            raise ValueError("Due date cannot be empty.")
        parsed_due = parse_date_safe(due_date_str)
        if not parsed_due:
            raise ValueError(f"Invalid due date format: '{due_date_str}'. Expected YYYY-MM-DD.")
        due_date_val = parsed_due.isoformat()
    else:
        due_date_val = inv_dict.get('due_date')

    raw_rate = terms_data.get('interest_rate_pct')
    if raw_rate is not None:
        try:
            rate_dec = quantize_currency(raw_rate)
            if rate_dec < Decimal('0.00'):
                raise ValueError()
            rate_val = float(rate_dec)
        except Exception:
            raise ValueError("Interest rate must be a non-negative percentage (>= 0.0%).")
    else:
        rate_val = float(inv_dict.get('interest_rate_pct') or 0.0)

    basis_val = str(terms_data.get('interest_calculation_basis') or inv_dict.get('interest_calculation_basis') or 'ANNUAL_SIMPLE').upper().strip()
    if basis_val not in VALID_BASES:
        raise ValueError(f"Invalid interest calculation basis. Must be one of: {', '.join(VALID_BASES)}")

    grace_val = terms_data.get('interest_grace_period_days')
    if grace_val is not None:
        try:
            grace_int = int(grace_val)
            if grace_int < 0:
                raise ValueError()
        except Exception:
            raise ValueError("Interest grace period must be a non-negative integer.")
    else:
        grace_int = int(inv_dict.get('interest_grace_period_days') or 0)

    notes = str(terms_data.get('notes') or '').strip()

    # Update database
    conn.execute(
        """UPDATE invoices
           SET due_date = ?, interest_rate_pct = ?, interest_calculation_basis = ?, interest_grace_period_days = ?
           WHERE id = ?""",
        (due_date_val, rate_val, basis_val, grace_int, inv_dict['id'])
    )

    log_audit_event(
        conn,
        event_type="INVOICE_TERMS_UPDATED",
        order_id=inv_dict['order_id'],
        actor_user_id=actor_user['id'],
        actor_role=actor_user['role'],
        before_state={
            "due_date": inv_dict.get('due_date'),
            "interest_rate_pct": inv_dict.get('interest_rate_pct'),
            "interest_calculation_basis": inv_dict.get('interest_calculation_basis'),
            "interest_grace_period_days": inv_dict.get('interest_grace_period_days')
        },
        after_state={
            "due_date": due_date_val,
            "interest_rate_pct": rate_val,
            "interest_calculation_basis": basis_val,
            "interest_grace_period_days": grace_int
        },
        justification=notes or f"Agreed payment terms updated for Invoice #{inv_dict['invoice_number']}.",
        ip_address=ip_address
    )

    return calculate_invoice_interest(conn, inv_dict['id'])
