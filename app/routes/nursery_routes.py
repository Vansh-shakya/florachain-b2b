"""
FloraChain B2B — Nursery Dashboard API Endpoints
Phase 12: Nursery Buyer Operations, Purchase Orders, Inbound Shipments, and Financial Balances
"""

from flask import Blueprint, request, jsonify
from app.models.database import get_connection
from app.services.auth_service import get_current_user, login_required
from app.services.nursery_dashboard_service import get_nursery_dashboard_data

nursery_bp = Blueprint('nursery', __name__, url_prefix='/api/nursery')


@nursery_bp.route('/dashboard', methods=['GET'])
@login_required
def get_nursery_dashboard():
    """
    Returns the real-time operational dashboard for the authenticated nursery buyer:
    - Active order counts and statuses
    - Inbound shipments & dock inspection tasks
    - Recent purchase orders
    - Invoice summary with due dates, overdue counts, and agreed late-payment interest
    - Authoritative financial ledger balances (Principal, Advances, Net Due)
    - Recent ledger transaction history
    - Active deal agreements
    
    Authorization: Strictly restricted to NURSERY and ADMIN roles.
    """
    user = get_current_user()
    if not user:
        return jsonify({
            "success": False,
            "error": "Authentication required. No active session found."
        }), 401

    role = (user.get('role') or '').upper()
    if role not in ('NURSERY', 'ADMIN'):
        return jsonify({
            "success": False,
            "error": f"Access denied: Role '{role}' is not authorized to access the Nursery Buyer Dashboard."
        }), 403

    conn = get_connection()
    try:
        data = get_nursery_dashboard_data(conn, user)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    except Exception as ex:
        return jsonify({
            "success": False,
            "error": f"Failed to retrieve nursery dashboard data: {str(ex)}"
        }), 500
    finally:
        conn.close()

