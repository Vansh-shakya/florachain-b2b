"""
FloraChain B2B — Authentication & Session Endpoints
Stage 2: Real Credential Authentication, Session-Based RBAC & Demo Mode Guardrails
"""

from flask import Blueprint, request, jsonify, session, current_app
import secrets
from werkzeug.security import check_password_hash
from app.models.database import get_connection
from app.services.auth_service import (
    get_current_user,
    login_required,
    require_role,
    can_confirm_delivery_as_party
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

DEMO_ROLES = [
    {
        "role": "NURSERY",
        "username": "nursery_amit",
        "business_name": "Green Meadows Landscape Nursery",
        "description": "Receiving nursery buyer & dock inspection officer. Can record physical counts and sign nursery confirmation."
    },
    {
        "role": "SUPPLIER",
        "username": "supplier_rajesh",
        "business_name": "GreenRoots Wholesale Farms",
        "description": "Plant wholesale grower & dispatch manager. Reviews counts and counter-signs delivery confirmation."
    },
    {
        "role": "ADMIN",
        "username": "admin_flora",
        "business_name": "FloraChain B2B Compliance & Audit Authority",
        "description": "Platform administrator. Can review audit ledger and approve formal corrections. Cannot bypass dual confirmation."
    }
]

# ============================================================================
# 1. REAL CREDENTIAL AUTHENTICATION
# ============================================================================

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticates a user with username (or email) and password using Werkzeug salted hashing.
    Enforces session fixation protection and sets secure session cookies.
    Rejects demo role parameter unless explicitly configured in local development mode.
    """
    data = request.get_json(silent=True) or {}
    raw_user = data.get('username') or data.get('email')
    username_or_email = str(raw_user).strip() if raw_user is not None else ''
    password = data.get('password')

    # Security check: users cannot gain a role merely by submitting a role name
    if 'role' in data and not username_or_email:
        return jsonify({
            "success": False,
            "error": "Cannot authenticate merely by role name. Username/email and password are required."
        }), 400

    if not username_or_email or not isinstance(password, str) or not password:
        return jsonify({
            "success": False,
            "error": "Both username/email and password are required and must be text strings."
        }), 400

    conn = get_connection()
    try:
        user = conn.execute(
            """SELECT id, username, email, password_hash, role, business_name 
               FROM users 
               WHERE username = ? OR email = ?""",
            (username_or_email, username_or_email)
        ).fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({
                "success": False,
                "error": "Invalid username/email or password."
            }), 401

        # Session fixation protection: clear previous session before establishing authenticated identity
        session.clear()
        session.permanent = True
        session['user_id'] = user["id"]
        session['role'] = user["role"]
        session['username'] = user["username"]
        session['csrf_token'] = secrets.token_hex(32)

        return jsonify({
            "success": True,
            "message": f"Successfully authenticated as {user['username']}.",
            "csrf_token": session['csrf_token'],
            "data": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"],
                "business_name": user["business_name"],
                "csrf_token": session['csrf_token']
            }
        })
    finally:
        conn.close()

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Clears authenticated session and returns confirmation.
    """
    session.clear()
    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })

@auth_bp.route('/csrf-token', methods=['GET'])
def get_csrf_token():
    """
    Returns or establishes the CSRF token for the current session.
    """
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return jsonify({
        "success": True,
        "csrf_token": session['csrf_token']
    })

@auth_bp.route('/me', methods=['GET'])
def get_current_user_profile():
    """
    Returns current authenticated user session data and permission capabilities.
    Returns 401 Unauthorized if not authenticated.
    """
    user = get_current_user()
    if not user:
        return jsonify({
            "success": False,
            "authenticated": False,
            "error": "Authentication required. No active session found."
        }), 401

    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)

    return jsonify({
        "success": True,
        "authenticated": True,
        "csrf_token": session['csrf_token'],
        "data": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "business_name": user["business_name"],
            "csrf_token": session['csrf_token']
        },
        "permissions": {
            "role": user["role"],
            "can_counter_sign_nursery": user["role"] == "NURSERY",
            "can_counter_sign_supplier": user["role"] == "SUPPLIER",
            "can_admin_corrections": user["role"] == "ADMIN",
            "unrestricted_admin_access": False  # Strictly forbidden
        }
    })

# ============================================================================
# 2. LOCAL DEMONSTRATION ROLE SWITCHER (STRICTLY GATED)
# ============================================================================

@auth_bp.route('/roles', methods=['GET'])
def get_available_roles():
    """
    Returns list of demonstration roles for local development demonstrations.
    Disabled by default outside explicitly configured local-development mode.
    """
    if not current_app.config.get('ALLOW_DEMO_ROLE_SWITCH', False):
        return jsonify({
            "success": False,
            "error": "Demonstration mode is disabled in this environment."
        }), 403

    return jsonify({
        "success": True,
        "data": DEMO_ROLES
    })

@auth_bp.route('/switch-role', methods=['POST'])
def switch_demo_role():
    """
    Role switcher for local demonstrations only.
    SECURITY RESTRICTIONS:
    - Disabled by default outside explicitly configured local-development mode (ALLOW_DEMO_ROLE_SWITCH=True).
    - Requires valid pre-configured role ('SUPPLIER', 'NURSERY', 'ADMIN').
    - Server-side authorization maps to seeded demonstration user with fixed privileges.
    - Prevents unrestricted administrator access: Admin role cannot counter-sign deliveries.
    """
    if not current_app.config.get('ALLOW_DEMO_ROLE_SWITCH', False):
        return jsonify({
            "success": False,
            "error": "Demonstration role switcher is disabled in this environment. It is restricted to explicitly configured local-development mode."
        }), 403

    data = request.get_json(silent=True) or {}
    role = (data.get('role') or '').upper().strip()

    valid_roles = {'NURSERY', 'SUPPLIER', 'ADMIN'}
    if role not in valid_roles:
        return jsonify({
            "success": False,
            "error": f"Invalid role '{role}'. Permitted demo roles: {', '.join(sorted(valid_roles))}"
        }), 400

    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT id, username, email, role, business_name FROM users WHERE role = ?",
            (role,)
        ).fetchone()
        if not user:
            return jsonify({
                "success": False,
                "error": f"No demo user configured for role '{role}'"
            }), 404

        session.clear()
        session.permanent = True
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['username'] = user['username']
        session['csrf_token'] = secrets.token_hex(32)

        return jsonify({
            "success": True,
            "message": f"Switched active demonstration role to {role}",
            "csrf_token": session['csrf_token'],
            "data": dict(user),
            "access_control": {
                "role": user["role"],
                "can_counter_sign_nursery": user["role"] == "NURSERY",
                "can_counter_sign_supplier": user["role"] == "SUPPLIER",
                "can_approve_corrections": user["role"] == "ADMIN",
                "unrestricted_admin_access": False  # Strictly forbidden
            }
        })
    finally:
        conn.close()

# ============================================================================
# 3. RBAC TEST & AUTHORIZATION GUARDRAIL ENDPOINTS
# ============================================================================

@auth_bp.route('/supplier-area', methods=['GET'])
@require_role('SUPPLIER')
def supplier_area():
    user = get_current_user()
    return jsonify({
        "success": True,
        "message": f"Welcome to the Supplier Area, {user['username']}.",
        "role": user["role"]
    })

@auth_bp.route('/nursery-area', methods=['GET'])
@require_role('NURSERY')
def nursery_area():
    user = get_current_user()
    return jsonify({
        "success": True,
        "message": f"Welcome to the Nursery Receiving Area, {user['username']}.",
        "role": user["role"]
    })

@auth_bp.route('/admin-area', methods=['GET'])
@require_role('ADMIN')
def admin_area():
    user = get_current_user()
    return jsonify({
        "success": True,
        "message": f"Welcome to the Compliance & Audit Area, {user['username']}.",
        "role": user["role"],
        "unrestricted_admin_access": False
    })

@auth_bp.route('/check-confirmation-permission', methods=['POST'])
@login_required
def check_confirmation_permission():
    """
    Checks if active authenticated user can counter-sign a physical delivery verification.
    Enforces Requirement 5: Administrators cannot impersonate either party or satisfy
    either of the two independent delivery confirmations.
    """
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    party_role = data.get('party_role')

    allowed, reason = can_confirm_delivery_as_party(user, party_role)
    if not allowed:
        return jsonify({
            "success": False,
            "allowed": False,
            "error": reason
        }), 403

    return jsonify({
        "success": True,
        "allowed": True,
        "party_role": party_role,
        "signatory": user["username"],
        "business_name": user["business_name"]
    })
