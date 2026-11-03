"""
FloraChain B2B — Phase 12 Nursery Dashboard Service
Provides authoritative, isolated dashboard metrics for the NURSERY role:
- Profile & counterparty supplier partnership info
- Active order counts and order statuses
- Orders awaiting dispatch / in-transit / delivery verification tasks
- Recent purchase orders with plant varieties and totals
- Invoices summary with contractual due dates, overdue tracking, and accrued interest
- Authoritative financial ledger summary (Principal, Advances, Net Due, Accrued Interest)
- Recent commercial ledger transactions
- Active deal agreements and payment schedules
- Multi-tenant counterparty isolation & role-based access control
"""

from decimal import Decimal
import datetime

from app.services.order_service import list_orders_for_user
from app.services.invoice_service import list_invoices_for_user
from app.services.interest_service import calculate_invoice_interest
from app.services.ledger_service import get_ledger_summary, get_ledger_entries
from app.services.agreement_service import list_agreements_for_user


def get_nursery_dashboard_data(conn, actor_user):
    """
    Assembles a complete, unified, real-time dashboard payload for an authenticated nursery buyer.
    
    Security & Authorization:
    - Enforces actor_user role in ('NURSERY', 'ADMIN').
    - Scopes all queries strictly to the authenticated nursery's user ID.
    - Prevents data leakage from other nurseries or unrelated supplier records.
    """
    if not actor_user:
        raise PermissionError("Authentication required to access Nursery Dashboard.")

    role = (actor_user.get('role') or '').upper()
    if role not in ('NURSERY', 'ADMIN'):
        raise PermissionError("Access denied: Only nursery buyers and platform administrators can access the Nursery Dashboard.")

    nursery_id = actor_user.get('id')

    # -------------------------------------------------------------------------
    # 1. Nursery Profile & Account Metadata
    # -------------------------------------------------------------------------
    user_row = conn.execute(
        "SELECT id, username, email, role, business_name FROM users WHERE id = ?",
        (nursery_id,)
    ).fetchone()

    profile = dict(user_row) if user_row else {
        "id": nursery_id,
        "username": actor_user.get('username', ''),
        "email": actor_user.get('email', ''),
        "role": "NURSERY",
        "business_name": actor_user.get('business_name', 'Nursery Partner')
    }

    # -------------------------------------------------------------------------
    # 2. Orders & Order Status Metrics
    # -------------------------------------------------------------------------
    all_orders = list_orders_for_user(conn, actor_user)

    active_statuses = {'PENDING', 'CONFIRMED', 'STAGED', 'DISPATCHED', 'IN_TRANSIT'}
    active_orders = [o for o in all_orders if (o.get('status') or '').upper() in active_statuses]
    awaiting_dispatch = [o for o in all_orders if (o.get('status') or '').upper() in {'CONFIRMED', 'STAGED'}]
    in_transit_orders = [o for o in all_orders if (o.get('status') or '').upper() in {'DISPATCHED', 'IN_TRANSIT'}]
    verified_orders = [o for o in all_orders if (o.get('status') or '').upper() in {'DELIVERED', 'LOCKED_VERIFIED'}]

    # Inbound shipments pending arrival or nursery dock inspection
    inbound_tasks = []
    for o in all_orders:
        status_up = (o.get('status') or '').upper()
        insp_status = (o.get('inspection_status') or '').upper()
        is_locked = bool(o.get('is_locked'))
        
        # Eligible for dock inspection if dispatched/in-transit or inspection is unlocked draft
        if status_up in {'DISPATCHED', 'IN_TRANSIT'} or (insp_status in {'DRAFT', 'PENDING_CONFIRMATION'} and not is_locked):
            inbound_tasks.append({
                "order_id": o['id'],
                "variety": o.get('variety', 'Mixed Varieties'),
                "ordered_qty": o.get('ordered_qty', 0),
                "delivered_qty": o.get('delivered_qty') or o.get('ordered_qty', 0),
                "sound_qty": o.get('sound_qty'),
                "damaged_qty": o.get('damaged_qty', 0),
                "truck_no": o.get('truck_no', 'Pending Assignment'),
                "driver_info": o.get('driver_info', 'Pending Driver Details'),
                "status": o.get('status'),
                "inspection_status": o.get('inspection_status', 'PENDING'),
                "is_locked": is_locked,
                "supplier_name": o.get('supplier_name', 'Wholesale Supplier')
            })

    # Recent orders summary (top 6)
    recent_orders = []
    for o in all_orders[:6]:
        recent_orders.append({
            "order_id": o['id'],
            "variety": o.get('variety', 'Assorted Plants'),
            "ordered_qty": o.get('ordered_qty', 0),
            "unit_price": o.get('unit_price', 0.0),
            "total_amount": o.get('total_amount', 0.0),
            "created_at": o.get('created_at', ''),
            "status": o.get('status'),
            "supplier_name": o.get('supplier_name', 'Wholesale Supplier'),
            "truck_no": o.get('truck_no', 'N/A'),
            "driver_info": o.get('driver_info', 'N/A'),
            "is_locked": bool(o.get('is_locked'))
        })

    # -------------------------------------------------------------------------
    # 3. Invoices, Due Dates & Contractual Late-Payment Interest
    # -------------------------------------------------------------------------
    all_invoices = list_invoices_for_user(conn, actor_user)
    
    invoices_summary_list = []
    overdue_count = 0
    upcoming_due_count = 0
    settled_invoices_count = 0

    for inv in all_invoices:
        inv_no = inv.get('invoice_number')
        interest_info = calculate_invoice_interest(conn, inv_no)
        due_status = interest_info.get('due_status', 'NO_DUE_DATE')

        if due_status == 'OVERDUE':
            overdue_count += 1
        elif due_status in ('NOT_DUE', 'IN_GRACE_PERIOD'):
            upcoming_due_count += 1
        elif due_status == 'SETTLED':
            settled_invoices_count += 1

        invoices_summary_list.append({
            "id": inv['id'],
            "invoice_number": inv_no,
            "order_id": inv.get('order_id'),
            "invoice_date": inv.get('invoice_date'),
            "total_amount": inv.get('total_amount', 0.0),
            "outstanding_principal": interest_info.get('outstanding_principal', inv.get('total_amount', 0.0)),
            "accrued_interest": interest_info.get('accrued_interest', 0.0),
            "total_payable": interest_info.get('total_amount_payable', inv.get('total_amount', 0.0)),
            "due_date": interest_info.get('due_date'),
            "due_status": due_status,
            "overdue_days": interest_info.get('overdue_days', 0),
            "interest_rate_pct": interest_info.get('agreed_rate_pct', 0.0),
            "supplier_name": inv.get('supplier_name', 'Wholesale Supplier'),
            "status": inv.get('status')
        })

    # -------------------------------------------------------------------------
    # 4. Authoritative Financial Balances (Ledger & Statement Summary)
    # -------------------------------------------------------------------------
    ledger_summary = get_ledger_summary(conn, actor_user, nursery_id=nursery_id)

    # -------------------------------------------------------------------------
    # 5. Recent Commercial Ledger Transactions (Top 6)
    # -------------------------------------------------------------------------
    ledger_entries_res = get_ledger_entries(conn, actor_user, {'order': 'desc'})
    recent_transactions = ledger_entries_res.get('entries', [])[:6]

    # -------------------------------------------------------------------------
    # 6. Deal Agreements & Payment Terms
    # -------------------------------------------------------------------------
    agreements_list = list_agreements_for_user(conn, actor_user)
    recent_agreements = []
    for agr in agreements_list[:5]:
        recent_agreements.append({
            "id": agr['id'],
            "agreement_ref": agr.get('agreement_ref'),
            "order_id": agr.get('order_id'),
            "supplier_name": agr.get('supplier_name', 'Wholesale Grower'),
            "total_order_value": agr.get('total_order_value', 0.0),
            "advance_percentage": agr.get('advance_percentage', 0.0),
            "advance_amount": agr.get('advance_amount', 0.0),
            "balance_amount": agr.get('balance_amount', 0.0),
            "payment_due_date": agr.get('payment_due_date'),
            "interest_rate_pct": agr.get('interest_rate_pct', 0.0),
            "status": agr.get('status')
        })

    return {
        "profile": profile,
        "metrics": {
            "total_orders": len(all_orders),
            "active_orders": len(active_orders),
            "awaiting_dispatch": len(awaiting_dispatch),
            "in_transit": len(in_transit_orders),
            "verified_orders": len(verified_orders),
            "inbound_tasks_count": len(inbound_tasks),
            "total_invoices": len(all_invoices),
            "overdue_invoices": overdue_count,
            "upcoming_due_invoices": upcoming_due_count,
            "settled_invoices": settled_invoices_count,
            "total_invoiced_gross": ledger_summary.get('total_invoiced_gross', 0.0),
            "total_payments_recorded": ledger_summary.get('total_payments_recorded', 0.0),
            "total_allocated_payments": ledger_summary.get('total_allocated_payments', 0.0),
            "total_unallocated_advances": ledger_summary.get('total_unallocated_advances', 0.0),
            "outstanding_principal": ledger_summary.get('outstanding_principal', 0.0),
            "net_balance_due": ledger_summary.get('net_balance_due', 0.0),
            "total_accrued_interest": ledger_summary.get('total_accrued_interest', 0.0),
            "total_amount_payable_with_interest": ledger_summary.get('total_amount_payable_with_interest', 0.0),
            "is_balanced": ledger_summary.get('is_balanced', True)
        },
        "inbound_tasks": inbound_tasks,
        "recent_orders": recent_orders,
        "invoices": invoices_summary_list,
        "recent_transactions": recent_transactions,
        "agreements": recent_agreements,
        "ledger_summary": ledger_summary
    }

