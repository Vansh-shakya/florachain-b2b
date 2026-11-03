"""
FloraChain B2B — Wholesale Invoicing API Routes
Phase 8: Verified Delivery Invoicing, Historical Price Immutability & Audit Trail
Phase 10: Contractual Due Date Tracking & Agreed Late-Payment Interest
"""

from flask import Blueprint, request, jsonify, session
from app.models.database import get_connection
from app.routes.auth_routes import get_current_user, login_required
from app.services.invoice_service import (
    generate_invoice_for_order,
    get_invoice_details,
    list_invoices_for_user,
    cancel_invoice,
    record_itemized_delivery_inspection
)

invoice_bp = Blueprint('invoices', __name__, url_prefix='/api')


@invoice_bp.route('/invoices', methods=['GET'])
@login_required
def list_invoices():
    """
    Lists invoices accessible to the authenticated user.
    Supports query parameters:
    - status: 'ALL', 'ISSUED', 'CANCELLED'
    - due_status: 'ALL', 'OVERDUE', 'NOT_DUE', 'SETTLED'
    - search: text matching invoice number, order id, nursery name, or supplier name
    """
    user = get_current_user()
    filters = {
        'status': request.args.get('status', 'ALL'),
        'due_status': request.args.get('due_status', 'ALL'),
        'search': request.args.get('search', '') or request.args.get('q', '')
    }

    conn = get_connection()
    try:
        invoices = list_invoices_for_user(conn, user, filters)
        return jsonify({
            "success": True,
            "count": len(invoices),
            "data": invoices
        }), 200
    finally:
        conn.close()


@invoice_bp.route('/invoices/<path:id_or_number>', methods=['GET'])
@login_required
def get_invoice(id_or_number):
    """
    Retrieves full itemized details of an issued invoice:
    - Frozen itemized plant varieties
    - Dual signatures and physical inspection metrics
    - Counterparty details and delivery manifest
    - Live payment allocations and interest calculations
    """
    user = get_current_user()
    conn = get_connection()
    try:
        invoice_data = get_invoice_details(conn, id_or_number, user)
        if not invoice_data:
            return jsonify({
                "success": False,
                "error": f"Invoice '{id_or_number}' not found."
            }), 404

        return jsonify({
            "success": True,
            "data": invoice_data
        }), 200
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    finally:
        conn.close()


@invoice_bp.route('/orders/<order_id>/invoice', methods=['POST'])
@login_required
def create_invoice_for_order(order_id):
    """
    Generates and issues a commercial wholesale invoice for a verified delivery order.
    Body parameters (optional):
    - tax_rate_pct: float (default 0.0)
    - discount_amount: float (default 0.0)
    - damage_charge_pct: float (default 0.0, damaged plants credited)
    - invoice_date: string YYYY-MM-DD
    - notes: string
    """
    user = get_current_user()
    data = request.get_json() or {}
    client_ip = request.remote_addr or '127.0.0.1'

    conn = get_connection()
    try:
        with conn:
            invoice_data = generate_invoice_for_order(conn, order_id, user, options=data, ip_address=client_ip)
        return jsonify({
            "success": True,
            "message": f"Invoice #{invoice_data['invoice']['invoice_number']} generated successfully.",
            "data": invoice_data
        }), 201
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    except ValueError as ve:
        err_msg = str(ve)
        if "Duplicate Invoice Conflict" in err_msg or "already been issued" in err_msg or "already exists" in err_msg:
            status_code = 409
        elif "explicit item-level" in err_msg or "Pro-rata" in err_msg:
            status_code = 422
        else:
            status_code = 400
        return jsonify({
            "success": False,
            "error": err_msg
        }), status_code
    except Exception as ex:
        return jsonify({
            "success": False,
            "error": f"Internal error during invoice generation: {str(ex)}"
        }), 500
    finally:
        conn.close()


@invoice_bp.route('/invoices/<path:id_or_number>/cancel', methods=['POST'])
@login_required
def cancel_invoice_route(id_or_number):
    """
    Cancels an issued commercial invoice.
    Body:
    - reason: required justification text
    """
    user = get_current_user()
    data = request.get_json() or {}
    reason = (data.get('reason') or '').strip()
    client_ip = request.remote_addr or '127.0.0.1'

    conn = get_connection()
    try:
        with conn:
            inv = cancel_invoice(conn, id_or_number, user, reason, ip_address=client_ip)
        inv_dict = inv.get('invoice', inv) if isinstance(inv, dict) else {}
        inv_number = inv_dict.get('invoice_number', id_or_number)
        return jsonify({
            "success": True,
            "message": f"Invoice #{inv_number} cancelled successfully.",
            "data": inv
        }), 200
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    except ValueError as ve:
        return jsonify({
            "success": False,
            "error": str(ve)
        }), 400
    finally:
        conn.close()


@invoice_bp.route('/orders/<order_id>/itemized-inspection', methods=['POST'])
@login_required
def record_itemized_inspection_route(order_id):
    """
    Records explicit item-level delivery, sound, and damaged counts for multi-variety orders.
    Body:
    - items: array of { order_item_id, delivered_qty, sound_qty, damaged_qty }
    """
    user = get_current_user()
    data = request.get_json() or {}
    items_data = data.get('items', [])
    client_ip = request.remote_addr or '127.0.0.1'

    conn = get_connection()
    try:
        res = record_itemized_delivery_inspection(conn, order_id, user, items_data, ip_address=client_ip)
        conn.commit()
        return jsonify({
            "success": True,
            "message": f"Itemized delivery inspection saved for Order #{order_id}.",
            "data": res
        }), 200
    except PermissionError as pe:
        conn.rollback()
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    except ValueError as ve:
        conn.rollback()
        return jsonify({
            "success": False,
            "error": str(ve)
        }), 422
    finally:
        conn.close()


@invoice_bp.route('/invoices/<path:id_or_number>/interest', methods=['GET'])
@login_required
def get_invoice_interest_route(id_or_number):
    """
    Returns late-payment interest calculation and breakdown for an invoice.
    Optional query parameter:
    - as_of_date: 'YYYY-MM-DD' (defaults to today)
    """
    user = get_current_user()
    as_of_date = request.args.get('as_of_date')

    conn = get_connection()
    try:
        from app.services.interest_service import calculate_invoice_interest
        
        # Verify access permission
        inv_details = get_invoice_details(conn, id_or_number, user)
        if not inv_details:
            return jsonify({
                "success": False,
                "error": f"Invoice '{id_or_number}' not found."
            }), 404

        interest_data = calculate_invoice_interest(conn, id_or_number, as_of_date=as_of_date)
        return jsonify({
            "success": True,
            "data": interest_data
        }), 200
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    finally:
        conn.close()


@invoice_bp.route('/invoices/<path:id_or_number>/interest-terms', methods=['POST'])
@login_required
def update_invoice_interest_terms_route(id_or_number):
    """
    Records or updates agreed payment due date and late-payment interest terms for an issued invoice.
    Body:
    - due_date: 'YYYY-MM-DD'
    - interest_rate_pct: number (>= 0.0)
    - interest_calculation_basis: 'ANNUAL_SIMPLE', 'MONTHLY_SIMPLE', 'DAILY_SIMPLE', 'NONE'
    - interest_grace_period_days: non-negative integer
    - notes: optional remarks / reason
    """
    user = get_current_user()
    data = request.get_json() or {}
    client_ip = request.remote_addr or '127.0.0.1'

    conn = get_connection()
    try:
        from app.services.interest_service import record_invoice_agreed_terms
        with conn:
            res = record_invoice_agreed_terms(conn, id_or_number, data, user, ip_address=client_ip)
        return jsonify({
            "success": True,
            "message": "Agreed invoice terms updated successfully.",
            "data": res
        }), 200
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    except ValueError as ve:
        return jsonify({
            "success": False,
            "error": str(ve)
        }), 400
    finally:
        conn.close()
