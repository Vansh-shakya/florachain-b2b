"""
FloraChain B2B — Authentication & Authorization Service
Stage 2: Session-based RBAC, Access Control Decorators & Party Signature Guardrails
"""

from functools import wraps
from flask import session, jsonify, g
from app.models.database import get_connection

def get_current_user():
    """
    Retrieves the currently authenticated user based on session['user_id'].
    Returns a dictionary of user details, or None if unauthenticated.
    Caches the lookup in Flask request context `g.current_user`.
    """
    if hasattr(g, 'current_user') and g.current_user is not None:
        return g.current_user

    user_id = session.get('user_id')
    if not user_id:
        g.current_user = None
        return None

    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT id, username, email, role, business_name FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if user:
            g.current_user = dict(user)
            return g.current_user
        else:
            # Stale session cleanup
            session.clear()
            g.current_user = None
            return None
    finally:
        conn.close()

def login_required(f):
    """
    Decorator: Enforces that a valid user session exists.
    Returns 401 Unauthorized if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({
                "success": False,
                "error": "Authentication required. Please log in with your credentials."
            }), 401
        return f(*args, **kwargs)
    return decorated_function

def require_role(*allowed_roles):
    """
    Decorator: Enforces that the authenticated user possesses one of the allowed roles.
    Returns 401 if unauthenticated, 403 if unauthorized for the role.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({
                    "success": False,
                    "error": "Authentication required. Please log in."
                }), 401

            if user['role'] not in allowed_roles:
                return jsonify({
                    "success": False,
                    "error": f"Forbidden: This action requires one of roles: {', '.join(allowed_roles)}. Your active role is '{user['role']}'."
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def can_confirm_delivery_as_party(user, party_role):
    """
    Validates whether the user is authorized to counter-sign a delivery verification as party_role.
    
    CRITICAL SECURITY INVARIANTS:
    1. party_role must strictly be 'SUPPLIER' or 'NURSERY'.
    2. user['role'] must match party_role exactly.
    3. Administrators (role == 'ADMIN') CANNOT impersonate either party or satisfy
       either of the two independent delivery confirmations.
    """
    if not user or not user.get('role'):
        return False, "User not authenticated."

    normalized_party = (party_role or '').upper().strip()
    if normalized_party not in ('SUPPLIER', 'NURSERY'):
        return False, f"Invalid delivery confirmation party role '{party_role}'. Must be SUPPLIER or NURSERY."

    if user['role'] == 'ADMIN':
        return False, "Security Violation: Administrators cannot impersonate either party or satisfy independent delivery confirmations."

    if user['role'] != normalized_party:
        return False, f"Forbidden: User with role '{user['role']}' cannot counter-sign as '{normalized_party}'."

    return True, None
