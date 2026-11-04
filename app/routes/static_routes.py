"""
FloraChain B2B — Static Asset & SPA Gateway Routes
Stage 1: Foundation Gateway serving existing frontend and API health
"""

import os
from flask import Blueprint, send_from_directory, jsonify, request

static_bp = Blueprint('static_routes', __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
STATIC_DIR = os.path.join(BASE_DIR, 'app', 'static')

@static_bp.route('/api/health', methods=['GET'])
def health():
    from app.models.database import get_active_dialect
    dialect = get_active_dialect()
    db_label = "PostgreSQL" if dialect == 'postgresql' else "SQLite (WAL mode)"
    return jsonify({
        "status": "ok",
        "service": "FloraChain B2B Backend Engine",
        "stage": "Stage 1 — SQLite Schema & Flask Foundation",
        "version": "1.0.0",
        "database": db_label,
        "dual_confirmation": True
    })

@static_bp.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@static_bp.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def serve_spa(path):
    # If hitting api/health without leading slash
    if path == 'api/health':
        return health()

    # Unknown API routes must return JSON 404 instead of falling back to SPA HTML
    if path.startswith('api/') or path == 'api':
        return jsonify({
            "success": False,
            "error": f"API endpoint '/{path}' not found."
        }), 404

    # Frontend SPA routes only support GET
    if request.method != 'GET':
        return jsonify({
            "success": False,
            "error": f"Method {request.method} not allowed for '/{path}'."
        }), 405

    # Serve static assets located in app/static/
    if path.startswith('app/static/'):
        rel_file = path[len('app/static/'):]
        return send_from_directory(STATIC_DIR, rel_file)

    # Direct file request from project root (e.g., index.html)
    target_file = os.path.join(BASE_DIR, path)
    if path and os.path.isfile(target_file):
        return send_from_directory(BASE_DIR, path)

    # Default fallback: Serve index.html SPA
    return send_from_directory(BASE_DIR, 'index.html')
