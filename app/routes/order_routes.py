"""
FloraChain B2B — Wholesale Order Management Endpoints
Phase 6: Multi-Variety Order Management & Itemized Order Lines
"""

from flask import Blueprint, request, jsonify
from app.models.database import get_connection
from app.services.auth_service import get_current_user, login_required
from app.services.order_service import (
    create_order,
    list_orders_for_user,
    get_order_details,
    list_nurseries_for_orders
)
from app.services.truck_service import (
    get_truck_loading_details,
    save_truck_loading,
    list_truck_manifests
)

order_bp = Blueprint('orders', __name__, url_prefix='/api')


@order_bp.route('/orders', methods=['GET'])
@login_required
def list_orders():
    """
    Returns platform wholesale orders accessible to the authenticated user.
    Enforces role isolation (Supplier vs Nursery vs Admin).
    Supports status filter and keyword search.
    """
    user = get_current_user()
    conn = get_connection()
    try:
        orders = list_orders_for_user(conn, user, request.args)
        return jsonify({
            "success": True,
            "count": len(orders),
            "data": orders
        })
    finally:
        conn.close()


@order_bp.route('/orders', methods=['POST'])
@login_required
def create_new_order():
    """
    Creates a new wholesale plant order with multi-variety itemized lines.
    Enforces role authorization (Suppliers and Admins only), positive integer quantities,
    line totals, and audit logging.
    """
    user = get_current_user()
    data = request.get_json() or {}
    ip_address = request.remote_addr or '127.0.0.1'
    conn = get_connection()
    try:
        with conn:
            order_details = create_order(conn, user, data, ip_address=ip_address)
        return jsonify({
            "success": True,
            "message": f"Order #{order_details['order']['id']} created successfully.",
            "data": order_details
        }), 201
    except ValueError as ve:
        return jsonify({
            "success": False,
            "error": str(ve)
        }), 400
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    except Exception as ex:
        return jsonify({
            "success": False,
            "error": f"Failed to create order: {str(ex)}"
        }), 500
    finally:
        conn.close()


@order_bp.route('/orders/<order_id>', methods=['GET'])
@login_required
def get_order(order_id):
    """
    Returns complete order details including:
    - Itemized order_items lines
    - Supplier and Nursery details
    - Delivery inspection and dual-party confirmations
    - Linked deal agreement
    """
    user = get_current_user()
    conn = get_connection()
    try:
        details = get_order_details(conn, order_id, user)
        if not details:
            return jsonify({
                "success": False,
                "error": f"Order #{order_id} not found."
            }), 404
        return jsonify({
            "success": True,
            "data": details
        })
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    finally:
        conn.close()


@order_bp.route('/orders/nurseries', methods=['GET'])
@login_required
def get_order_nurseries():
    """
    Returns registered nursery partners available for order placement.
    """
    conn = get_connection()
    try:
        nurseries = list_nurseries_for_orders(conn)
        return jsonify({
            "success": True,
            "count": len(nurseries),
            "data": nurseries
        })
    finally:
        conn.close()


@order_bp.route('/orders/<order_id>/loading', methods=['GET'])
@login_required
def get_order_loading(order_id):
    """
    Returns truck loading manifest details for an order:
    - Ordered varieties, loaded quantities, remaining counts
    - Vehicle registration (truck_no) and driver info
    - Editability and lock status
    """
    user = get_current_user()
    conn = get_connection()
    try:
        details = get_truck_loading_details(conn, order_id, user)
        if not details:
            return jsonify({
                "success": False,
                "error": f"Order #{order_id} not found."
            }), 404
        return jsonify({
            "success": True,
            "data": details
        })
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    finally:
        conn.close()


@order_bp.route('/orders/<order_id>/loading', methods=['POST'])
@login_required
def update_order_loading(order_id):
    """
    Saves loaded quantities, vehicle registration, and driver details.
    Enforces supplier ownership, non-negative loaded counts, and max-order constraints.
    Supports staging save or full vehicle dispatch.
    """
    user = get_current_user()
    data = request.get_json() or {}
    ip_address = request.remote_addr or '127.0.0.1'
    conn = get_connection()
    try:
        with conn:
            details = save_truck_loading(conn, order_id, user, data, ip_address=ip_address)
        action_msg = "Truck dispatched successfully." if data.get('dispatch') else "Truck loading progress saved."
        return jsonify({
            "success": True,
            "message": action_msg,
            "data": details
        }), 200
    except ValueError as ve:
        return jsonify({
            "success": False,
            "error": str(ve)
        }), 400
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    except Exception as ex:
        return jsonify({
            "success": False,
            "error": f"Failed to save truck loading: {str(ex)}"
        }), 500
    finally:
        conn.close()


@order_bp.route('/truck-loadings', methods=['GET'])
@login_required
def list_truck_loadings():
    """
    Returns platform wholesale vehicle manifests and loading board orders.
    Enforces role isolation (Suppliers see their trucks, Nurseries see their deliveries, Admins see all).
    """
    user = get_current_user()
    conn = get_connection()
    try:
        manifests = list_truck_manifests(conn, user, request.args)
        return jsonify({
            "success": True,
            "count": len(manifests),
            "data": manifests
        })
    finally:
        conn.close()

