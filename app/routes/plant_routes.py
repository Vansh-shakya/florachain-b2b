"""
FloraChain B2B — Plant Catalog & Inventory Endpoints
Phase 5: Plant Management Backend API
"""

from flask import Blueprint, request, jsonify
from app.models.database import get_connection
from app.services.auth_service import get_current_user, login_required, require_role
from app.services.plant_service import (
    list_plants,
    get_plant_by_id,
    create_plant,
    update_plant
)

plant_bp = Blueprint('plants', __name__, url_prefix='/api')


@plant_bp.route('/plants', methods=['GET'])
@login_required
def get_plants_list():
    """
    Returns wholesale plant catalog records.
    Supports filtering by search query (q/search), category, status, supplier_id, and scope (e.g. scope=mine).
    """
    user = get_current_user()
    filters = {
        'search': request.args.get('search') or request.args.get('q'),
        'category': request.args.get('category'),
        'status': request.args.get('status'),
        'supplier_id': request.args.get('supplier_id'),
        'scope': request.args.get('scope')
    }

    conn = get_connection()
    try:
        plants = list_plants(conn, user, filters=filters)
        return jsonify({
            "success": True,
            "count": len(plants),
            "data": plants
        })
    finally:
        conn.close()


@plant_bp.route('/plants/<int:plant_id>', methods=['GET'])
@login_required
def get_plant_detail(plant_id):
    """
    Retrieves full details of a single plant record by ID.
    """
    user = get_current_user()
    conn = get_connection()
    try:
        plant = get_plant_by_id(conn, plant_id, user=user)
        if not plant:
            return jsonify({
                "success": False,
                "error": f"Plant #{plant_id} not found."
            }), 404

        return jsonify({
            "success": True,
            "data": plant
        })
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    finally:
        conn.close()


@plant_bp.route('/plants', methods=['POST'])
@login_required
@require_role('SUPPLIER')
def create_new_plant():
    """
    Creates a new plant in the wholesale catalog.
    Enforces that the supplier identity is taken strictly from the authenticated session.
    """
    user = get_current_user()
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({
            "success": False,
            "error": "Request body must be valid JSON."
        }), 400

    conn = get_connection()
    try:
        with conn:
            plant = create_plant(conn, user, data)
        return jsonify({
            "success": True,
            "message": f"Plant '{plant['common_name']}' created successfully.",
            "data": plant
        }), 201
    except ValueError as ve:
        return jsonify({
            "success": False,
            "error": str(ve)
        }), 422
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    finally:
        conn.close()


@plant_bp.route('/plants/<int:plant_id>', methods=['PUT', 'POST'])
@login_required
@require_role('SUPPLIER')
def update_existing_plant(plant_id):
    """
    Updates an existing plant record.
    Enforces ownership: only the creator supplier can modify the record.
    """
    user = get_current_user()
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({
            "success": False,
            "error": "Request body must be valid JSON."
        }), 400

    conn = get_connection()
    try:
        with conn:
            plant = update_plant(conn, plant_id, user, data)
        return jsonify({
            "success": True,
            "message": f"Plant '{plant['common_name']}' updated successfully.",
            "data": plant
        })
    except ValueError as ve:
        err_msg = str(ve)
        status_code = 404 if "not found" in err_msg.lower() else 422
        return jsonify({
            "success": False,
            "error": err_msg
        }), status_code
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    finally:
        conn.close()

