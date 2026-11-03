"""
FloraChain B2B — Physical Inspection & Dual Confirmation Endpoints
Stage 3: Database-Backed Delivery Verification, Dual Counter-Signatures & Audit Trail
"""

from flask import Blueprint, request, jsonify
from app.models.database import get_connection
from app.services.auth_service import get_current_user, login_required
from app.services.inspection_service import (
    create_or_update_inspection,
    confirm_inspection_by_party,
    get_inspection_details,
    import_localstorage_draft
)
from app.services.audit_service import get_audit_trail_for_order

inspection_bp = Blueprint('inspections', __name__, url_prefix='/api')

@inspection_bp.route('/orders/<order_id>/inspection', methods=['POST'])
@login_required
def save_inspection(order_id):
    """
    Nursery dock receiving officer submits physical arrival plant counts.
    Enforces:
    - Valid non-negative whole integers
    - sound_qty + damaged_qty == delivered_qty
    - Nursery role and order assignment
    - Rejection if already locked (403 Forbidden)
    """
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    try:
        delivered_raw = data.get("delivered_qty")
        sound_raw = data.get("sound_qty")
        damaged_raw = data.get("damaged_qty")

        # Reject booleans or missing quantities
        if isinstance(delivered_raw, bool) or isinstance(sound_raw, bool) or isinstance(damaged_raw, bool):
            raise TypeError("Boolean values are not valid quantities.")

        delivered_qty = int(delivered_raw)
        sound_qty = int(sound_raw)
        damaged_qty = int(damaged_raw)
        damage_notes = str(data.get("damage_notes", ""))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "All quantities must be valid whole non-negative integers."
        }), 422

    conn = get_connection()
    try:
        with conn:
            details = create_or_update_inspection(
                conn, order_id, user, delivered_qty, sound_qty, damaged_qty, 
                damage_notes, request.remote_addr or "127.0.0.1"
            )
        return jsonify({
            "success": True,
            "message": f"Physical arrival inspection for Order #{order_id} saved successfully.",
            "data": details
        })
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 422
    except PermissionError as pe:
        return jsonify({"success": False, "error": str(pe)}), 403
    finally:
        conn.close()

@inspection_bp.route('/orders/<order_id>/confirm', methods=['POST'])
@login_required
def confirm_inspection(order_id):
    """
    Submits independent party counter-signature for delivery verification.
    Enforces:
    - Independent authenticated users (NURSERY and SUPPLIER)
    - Order ownership/assignment
    - Prevention of duplicate confirmation (409 Conflict)
    - Atomic locking when both independent confirmations are in place
    """
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    party_role = (data.get("party_role") or user["role"]).upper().strip()
    signature_note = str(data.get("signature_note", ""))

    conn = get_connection()
    try:
        with conn:
            details = confirm_inspection_by_party(
                conn, order_id, user, party_role, signature_note, request.remote_addr or "127.0.0.1"
            )
        return jsonify({
            "success": True,
            "message": f"Counter-signature recorded by {party_role} for Order #{order_id}.",
            "data": details
        })
    except ValueError as ve:
        # Conflict / duplicate confirmation or not found
        err_msg = str(ve)
        status_code = 404 if "not found" in err_msg.lower() else 409
        return jsonify({"success": False, "error": err_msg}), status_code
    except PermissionError as pe:
        return jsonify({"success": False, "error": str(pe)}), 403
    finally:
        conn.close()

@inspection_bp.route('/orders/<order_id>/confirmations', methods=['GET'])
@login_required
def get_order_confirmations(order_id):
    """
    Returns confirmation status and signatures for an order.
    Enforces object-level party authorization (Supplier, Nursery, Admin).
    """
    user = get_current_user()
    conn = get_connection()
    try:
        order = conn.execute(
            "SELECT id, supplier_user_id, nursery_user_id FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()
        if not order:
            return jsonify({"success": False, "error": f"Order #{order_id} not found."}), 404

        if user["role"] != "ADMIN" and user["id"] not in (order["supplier_user_id"], order["nursery_user_id"]):
            return jsonify({
                "success": False,
                "error": f"Unauthorized: You do not have permission to view confirmation history for Order #{order_id}."
            }), 403

        details = get_inspection_details(conn, order_id)
        if not details:
            return jsonify({"success": False, "error": f"Order #{order_id} not found."}), 404
        return jsonify({
            "success": True,
            "order_id": order_id,
            "is_locked": details["is_locked"],
            "nursery_confirmed": details["nursery_confirmed"],
            "supplier_confirmed": details["supplier_confirmed"],
            "confirmations": details["confirmations"]
        })
    finally:
        conn.close()

@inspection_bp.route('/orders/<order_id>/audit', methods=['GET'])
@login_required
def get_order_audit(order_id):
    """
    Returns complete chronological append-only audit trail for an order.
    Enforces object-level party authorization (Supplier, Nursery, Admin).
    """
    user = get_current_user()
    conn = get_connection()
    try:
        order = conn.execute(
            "SELECT id, supplier_user_id, nursery_user_id FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()
        if not order:
            return jsonify({"success": False, "error": f"Order #{order_id} not found."}), 404

        if user["role"] != "ADMIN" and user["id"] not in (order["supplier_user_id"], order["nursery_user_id"]):
            return jsonify({
                "success": False,
                "error": f"Unauthorized: You do not have permission to view audit history for Order #{order_id}."
            }), 403

        events = get_audit_trail_for_order(conn, order_id)
        return jsonify({
            "success": True,
            "order_id": order_id,
            "count": len(events),
            "data": events
        })
    finally:
        conn.close()

@inspection_bp.route('/inspections/import-local', methods=['POST'])
@login_required
def import_local():
    """
    Safely imports client-side localStorage drafts.
    Treated as UNTRUSTED legacy data: NEVER imported as pre-verified or locked.
    """
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    conn = get_connection()
    try:
        with conn:
            details = import_localstorage_draft(conn, data, user, request.remote_addr or "127.0.0.1")
        return jsonify({
            "success": True,
            "message": "Local draft safely registered as unconfirmed record (dual confirmation required).",
            "data": details
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 422
    finally:
        conn.close()
