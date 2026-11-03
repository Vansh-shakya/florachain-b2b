"""
FloraChain B2B — Wholesale Payment API Routes
Phase 9: Payment Management, Advance Tracking, Overpayment Prevention & Audit Reversals
"""

from flask import Blueprint, request, jsonify, session
from app.models.database import get_connection
from app.routes.auth_routes import get_current_user, login_required
from app.services.payment_service import (
    record_payment,
    allocate_advance_payment,
    reverse_payment,
    get_payment_details,
    list_payments_for_user,
    get_invoice_payment_summary,
    get_order_payment_summary
)

payment_bp = Blueprint('payments', __name__, url_prefix='/api')


@payment_bp.route('/payments', methods=['GET'])
@login_required
def list_payments():
    """
    Lists payments accessible to the authenticated user.
    Supports query filters:
    - status: 'ALL', 'RECORDED', 'REVERSED'
    - payment_method: 'ALL', 'BANK_TRANSFER', 'UPI', 'CHEQUE', 'CASH', 'OTHER'
    - payment_type: 'ALL', 'INVOICE_PAYMENT', 'ADVANCE_PAYMENT'
    - search: search text matching payment number, reference, notes, counterparty, or invoice
    - invoice_id: filter by specific invoice
    - order_id: filter by specific wholesale order
    """
    user = get_current_user()
    filters = {
        'status': request.args.get('status', 'ALL'),
        'payment_method': request.args.get('payment_method', request.args.get('method', 'ALL')),
        'payment_type': request.args.get('payment_type', request.args.get('type', 'ALL')),
        'search': request.args.get('search', '') or request.args.get('q', ''),
        'invoice_id': request.args.get('invoice_id', ''),
        'order_id': request.args.get('order_id', '')
    }

    conn = get_connection()
    try:
        result = list_payments_for_user(conn, user, filters)
        return jsonify({
            "success": True,
            "count": result["count"],
            "kpi": result["kpi"],
            "data": result["payments"]
        }), 200
    finally:
        conn.close()


@payment_bp.route('/payments/<path:id_or_number>', methods=['GET'])
@login_required
def get_payment(id_or_number):
    """
    Retrieves full details for a payment record including allocations and counterparty information.
    """
    user = get_current_user()
    conn = get_connection()
    try:
        payment_data = get_payment_details(conn, id_or_number, user)
        if not payment_data:
            return jsonify({
                "success": False,
                "error": f"Payment '{id_or_number}' not found."
            }), 404

        return jsonify({
            "success": True,
            "data": payment_data
        }), 200
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    finally:
        conn.close()


@payment_bp.route('/payments', methods=['POST'])
@login_required
def create_payment():
    """
    Records an incoming payment or advance against an issued invoice or wholesale order.
    Body Parameters:
    - invoice_id (optional if advance payment)
    - order_id (optional if direct invoice payment)
    - nursery_user_id (optional if order/invoice provided)
    - amount: positive number (> 0)
    - payment_method: 'BANK_TRANSFER', 'UPI', 'CHEQUE', 'CASH', 'OTHER'
    - reference_number: transaction / UTR / cheque / bank reference
    - payment_date: 'YYYY-MM-DD' (defaults to today)
    - payment_type: 'INVOICE_PAYMENT' or 'ADVANCE_PAYMENT'
    - notes: optional payment notes
    """
    user = get_current_user()
    payload = request.get_json() or {}
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')

    conn = get_connection()
    try:
        with conn:
            payment_record = record_payment(conn, payload, user, ip_address=ip_address)
        return jsonify({
            "success": True,
            "message": f"Payment #{payment_record['payment']['payment_number']} recorded successfully.",
            "data": payment_record
        }), 201
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    except ValueError as ve:
        err_msg = str(ve)
        status_code = 409 if "already been recorded" in err_msg or "Duplicate" in err_msg else 400
        return jsonify({
            "success": False,
            "error": err_msg
        }), status_code
    except Exception as ex:
        return jsonify({
            "success": False,
            "error": f"Internal error recording payment: {str(ex)}"
        }), 500
    finally:
        conn.close()


@payment_bp.route('/payments/<path:id_or_number>/reverse', methods=['POST'])
@login_required
def reverse_payment_endpoint(id_or_number):
    """
    Auditably reverses an existing payment:
    - Requires non-empty 'reason'
    - Restores outstanding balances on all associated invoices
    - Logs audit trail
    """
    user = get_current_user()
    payload = request.get_json() or {}
    reason = payload.get('reason') or payload.get('reversal_reason', '')
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')

    conn = get_connection()
    try:
        with conn:
            reversed_data = reverse_payment(conn, id_or_number, reason, user, ip_address=ip_address)
        return jsonify({
            "success": True,
            "message": f"Payment #{reversed_data['payment']['payment_number']} has been reversed.",
            "data": reversed_data
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
    except Exception as ex:
        return jsonify({
            "success": False,
            "error": f"Internal error reversing payment: {str(ex)}"
        }), 500
    finally:
        conn.close()


@payment_bp.route('/payments/<path:id_or_number>/allocate', methods=['POST'])
@login_required
def allocate_advance(id_or_number):
    """
    Allocates an unallocated advance payment to a specific issued invoice.
    Body Parameters:
    - invoice_id: target invoice id or number
    - amount: amount to allocate (> 0)
    """
    user = get_current_user()
    payload = request.get_json() or {}
    invoice_id = payload.get('invoice_id')
    amount = payload.get('amount')
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')

    conn = get_connection()
    try:
        with conn:
            result = allocate_advance_payment(conn, id_or_number, invoice_id, amount, user, ip_address=ip_address)
        return jsonify({
            "success": True,
            "message": f"Advance successfully allocated to invoice.",
            "data": result
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
    except Exception as ex:
        return jsonify({
            "success": False,
            "error": f"Internal error allocating advance: {str(ex)}"
        }), 500
    finally:
        conn.close()


@payment_bp.route('/invoices/<path:id_or_number>/payments', methods=['GET'])
@login_required
def get_invoice_payments(id_or_number):
    """
    Returns payment summary and all active allocations for an invoice.
    """
    user = get_current_user()
    conn = get_connection()
    try:
        summary = get_invoice_payment_summary(conn, id_or_number)
        if not summary:
            return jsonify({
                "success": False,
                "error": f"Invoice '{id_or_number}' not found."
            }), 404

        return jsonify({
            "success": True,
            "data": summary
        }), 200
    finally:
        conn.close()


@payment_bp.route('/orders/<path:order_id>/payments', methods=['GET'])
@login_required
def get_order_payments(order_id):
    """
    Returns all payments, advances, and invoice settlements related to a wholesale order.
    """
    user = get_current_user()
    conn = get_connection()
    try:
        summary = get_order_payment_summary(conn, order_id, user)
        if not summary:
            return jsonify({
                "success": False,
                "error": f"Order '{order_id}' not found."
            }), 404

        return jsonify({
            "success": True,
            "data": summary
        }), 200
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    finally:
        conn.close()

