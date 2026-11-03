"""
FloraChain B2B — Digital Deal Agreement & Payment Terms Endpoints
Stage: Digital Deal Agreement & Payment Terms

Provides RESTful endpoints for:
- Querying and listing deal agreements
- Viewing detailed terms, dual approval states, and audit trails
- Creating agreements with server-calculated advance, balance, and interest terms
- Independent in-app commercial approval by Supplier and Nursery
- Versioned amendment workflow on agreed records
"""

from flask import Blueprint, request, jsonify
from app.models.database import get_connection
from app.services.auth_service import get_current_user, login_required
from app.services.agreement_service import (
    create_deal_agreement,
    get_agreement_details,
    list_agreements_for_user,
    approve_deal_agreement,
    create_deal_amendment,
    update_draft_agreement
)

agreement_bp = Blueprint('agreements', __name__, url_prefix='/api')

@agreement_bp.route('/agreements', methods=['GET'])
@login_required
def list_agreements():
    """
    Lists digital deal agreements accessible to the authenticated user.
    """
    user = get_current_user()
    order_id = request.args.get('order_id')
    conn = get_connection()
    try:
        agreements = list_agreements_for_user(conn, user, order_id=order_id)
        return jsonify({
            "success": True,
            "count": len(agreements),
            "data": agreements
        })
    finally:
        conn.close()

@agreement_bp.route('/agreements/<path:id_or_ref>', methods=['GET'])
@login_required
def get_agreement(id_or_ref):
    """
    Retrieves full details of a digital deal agreement including approvals and legal disclaimer.
    """
    user = get_current_user()
    conn = get_connection()
    try:
        details = get_agreement_details(conn, id_or_ref)
        if not details:
            return jsonify({
                "success": False,
                "error": f"Deal agreement '{id_or_ref}' not found."
            }), 404

        # Access check: user must be supplier, nursery, or admin
        if user['role'] != 'ADMIN' and user['id'] not in (details['supplier_user_id'], details['nursery_user_id']):
            return jsonify({
                "success": False,
                "error": "Access forbidden: You are not an assigned party to this agreement."
            }), 403

        return jsonify({
            "success": True,
            "data": details
        })
    finally:
        conn.close()

@agreement_bp.route('/orders/<order_id>/agreement', methods=['GET'])
@login_required
def get_order_active_agreement(order_id):
    """
    Retrieves the most recent / active deal agreement for a specific order.
    """
    user = get_current_user()
    conn = get_connection()
    try:
        agreements = list_agreements_for_user(conn, user, order_id=order_id)
        if not agreements:
            return jsonify({
                "success": True,
                "data": None,
                "message": f"No deal agreement registered yet for Order #{order_id}."
            })
        # Return newest version first
        return jsonify({
            "success": True,
            "data": agreements[0]
        })
    finally:
        conn.close()

@agreement_bp.route('/agreements', methods=['POST'])
@login_required
def create_agreement_endpoint():
    """
    Creates a new digital deal agreement with server-calculated advance and interest terms.
    """
    user = get_current_user()
    data = request.get_json() or {}
    order_id = data.get('order_id')

    if not order_id:
        return jsonify({
            "success": False,
            "error": "Field 'order_id' is required."
        }), 422

    ip_address = request.remote_addr or "127.0.0.1"
    conn = get_connection()
    try:
        with conn:
            agreement = create_deal_agreement(
                conn,
                order_id=order_id,
                terms_data=data,
                creator_user=user,
                ip_address=ip_address,
                auto_approve=data.get('auto_approve', True)
            )
        return jsonify({
            "success": True,
            "message": f"Deal agreement {agreement['agreement_ref']} successfully created.",
            "data": agreement
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except PermissionError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    finally:
        conn.close()

@agreement_bp.route('/agreements/<int:agreement_id>/approve', methods=['POST'])
@login_required
def approve_agreement_endpoint(agreement_id):
    """
    Registers an in-app commercial approval by the authenticated party.
    Atomically finalizes status to 'AGREED' when both Supplier and Nursery approve.
    """
    user = get_current_user()
    data = request.get_json() or {}
    notes = data.get('notes', '')
    ip_address = request.remote_addr or "127.0.0.1"

    conn = get_connection()
    try:
        with conn:
            updated = approve_deal_agreement(
                conn,
                agreement_id=agreement_id,
                user=user,
                notes=notes,
                ip_address=ip_address
            )
        msg = f"Agreement {updated['agreement_ref']} permanently finalized & agreed." if updated['is_agreed'] else f"Approval recorded for {updated['agreement_ref']}; awaiting counterparty."
        return jsonify({
            "success": True,
            "message": msg,
            "data": updated
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except PermissionError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    finally:
        conn.close()

@agreement_bp.route('/agreements/<int:agreement_id>/amend', methods=['POST'])
@login_required
def amend_agreement_endpoint(agreement_id):
    """
    Creates a versioned amendment (v2, v3) from an existing agreed agreement.
    Preserves historical agreement intact and starts a new dual-approval cycle.
    """
    user = get_current_user()
    data = request.get_json() or {}
    reason = data.get('reason', '')
    ip_address = request.remote_addr or "127.0.0.1"

    if not reason or not str(reason).strip():
        return jsonify({
            "success": False,
            "error": "Mandatory amendment reason / justification is required."
        }), 422

    conn = get_connection()
    try:
        with conn:
            amended = create_deal_amendment(
                conn,
                agreement_id=agreement_id,
                revised_terms=data,
                user=user,
                reason=reason,
                ip_address=ip_address
            )
        return jsonify({
            "success": True,
            "message": f"Versioned amendment {amended['agreement_ref']} created and awaiting counterparty approval.",
            "data": amended
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except PermissionError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    finally:
        conn.close()

@agreement_bp.route('/agreements/<int:agreement_id>', methods=['PUT', 'POST'])
@login_required
def update_agreement_endpoint(agreement_id):
    """
    Updates an unfinalized deal agreement. Rejects ordinary edits if agreement is already AGREED.
    """
    user = get_current_user()
    data = request.get_json() or {}
    ip_address = request.remote_addr or "127.0.0.1"

    conn = get_connection()
    try:
        with conn:
            updated = update_draft_agreement(
                conn,
                agreement_id=agreement_id,
                revised_terms=data,
                user=user,
                ip_address=ip_address
            )
        return jsonify({
            "success": True,
            "message": f"Deal agreement {updated['agreement_ref']} updated.",
            "data": updated
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except PermissionError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    finally:
        conn.close()
