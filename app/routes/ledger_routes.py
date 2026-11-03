"""
FloraChain B2B — Phase 11: Ledger & Transaction History API Routes
Endpoints:
- GET /api/ledger: Chronological transaction feed with multi-parameter filtering & balance summary
- GET /api/ledger/summary: Standalone authoritative business balance summary & consistency metrics
"""

from flask import Blueprint, request, jsonify
from app.models.database import get_connection
from app.routes.auth_routes import get_current_user, login_required
from app.services.ledger_service import (
    get_ledger_entries,
    get_ledger_summary
)

ledger_bp = Blueprint('ledger', __name__, url_prefix='/api')


@ledger_bp.route('/ledger', methods=['GET'])
@login_required
def list_ledger_transactions():
    """
    Returns unified chronological ledger transactions and balance summary
    scoped to the authenticated user's authorized business relationships.
    Query Parameters:
    - nursery_id: filter by specific client nursery
    - type / transaction_type: filter by transaction type
    - start_date: filter entries >= start_date (YYYY-MM-DD)
    - end_date: filter entries <= end_date (YYYY-MM-DD)
    - status: 'ALL', 'ACTIVE', 'REVERSED', 'CANCELLED'
    - search / q: text query matching reference numbers, order ID, invoice, party
    - order: 'desc' (default: newest first) or 'asc' (chronological forward)
    """
    user = get_current_user()
    filters = {
        'nursery_id': request.args.get('nursery_id'),
        'type': request.args.get('type') or request.args.get('transaction_type', 'ALL'),
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'status': request.args.get('status', 'ALL'),
        'search': request.args.get('search') or request.args.get('q', ''),
        'order': request.args.get('order', 'desc')
    }

    conn = get_connection()
    try:
        result = get_ledger_entries(conn, user, filters)
        return jsonify({
            "success": True,
            "count": result["count"],
            "total_unfiltered": result["total_records_unfiltered"],
            "summary": result["summary"],
            "counterparties": result["counterparties"],
            "data": result["entries"]
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
            "error": f"Internal error retrieving ledger transactions: {str(ex)}"
        }), 500
    finally:
        conn.close()


@ledger_bp.route('/ledger/summary', methods=['GET'])
@login_required
def get_ledger_summary_route():
    """
    Returns standalone business balance summary figures calculated from authoritative database records.
    Query Parameters:
    - nursery_id: optional filter by specific nursery client
    """
    user = get_current_user()
    nursery_id = request.args.get('nursery_id')
    if nursery_id is not None and str(nursery_id).strip() != '' and str(nursery_id).upper() != 'ALL':
        try:
            nursery_id = int(nursery_id)
        except ValueError:
            nursery_id = None
    else:
        nursery_id = None

    conn = get_connection()
    try:
        summary = get_ledger_summary(conn, user, nursery_id)
        return jsonify({
            "success": True,
            "data": summary
        }), 200
    except PermissionError as pe:
        return jsonify({
            "success": False,
            "error": str(pe)
        }), 403
    except Exception as ex:
        return jsonify({
            "success": False,
            "error": f"Internal error calculating ledger balance summary: {str(ex)}"
        }), 500
    finally:
        conn.close()

