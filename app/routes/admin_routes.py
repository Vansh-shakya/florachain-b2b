"""
FloraChain B2B — Administrator Correction & Audit Review Endpoints
"""

from flask import Blueprint, request, jsonify
from app.models.database import get_connection
from app.services.auth_service import get_current_user as get_authenticated_user
from app.services.inspection_service import approve_correction

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@admin_bp.route('/corrections', methods=['GET'])
def list_pending_corrections():
    user = get_authenticated_user()
    if not user:
        return jsonify({"success": False, "error": "Authentication required."}), 401
    if user["role"] != "ADMIN":
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403

    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT c.*, 
                   di.order_id,
                   u.username as requester_name,
                   u.business_name as requester_business
            FROM inspection_corrections c
            JOIN delivery_inspections di ON c.inspection_id = di.id
            JOIN users u ON c.requested_by = u.id
            WHERE c.status = 'PENDING'
            ORDER BY c.created_at ASC
        """).fetchall()

        corrections = [dict(r) for r in rows]
        return jsonify({"success": True, "count": len(corrections), "data": corrections})
    finally:
        conn.close()

@admin_bp.route('/corrections/<int:corr_id>/approve', methods=['POST'])
def approve_order_correction(corr_id):
    user = get_authenticated_user()
    if not user:
        return jsonify({"success": False, "error": "Authentication required."}), 401
    if user["role"] != "ADMIN":
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403

    conn = get_connection()
    try:
        with conn:
            details = approve_correction(conn, corr_id, user, request.remote_addr or "127.0.0.1")
        return jsonify({
            "success": True,
            "message": f"Correction #{corr_id} approved. Historical audit log updated.",
            "data": details
        })
    except (ValueError, PermissionError) as e:
        return jsonify({"success": False, "error": str(e)}), 422
    finally:
        conn.close()

@admin_bp.route('/corrections/<int:corr_id>/reject', methods=['POST'])
def reject_order_correction(corr_id):
    user = get_authenticated_user()
    if not user:
        return jsonify({"success": False, "error": "Authentication required."}), 401
    if user["role"] != "ADMIN":
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403

    data = request.get_json(silent=True) or {}
    reject_reason = data.get("reason", "Rejected by administrator.")

    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """UPDATE inspection_corrections
                   SET status = 'REJECTED', approved_by = ?, resolved_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (user["id"], corr_id)
            )
        return jsonify({"success": True, "message": f"Correction #{corr_id} rejected."})
    finally:
        conn.close()
