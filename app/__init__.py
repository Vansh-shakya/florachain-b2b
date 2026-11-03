"""
FloraChain B2B — Flask Application Factory
Phase 13: Hardened Flask Application Factory, Centralized Config, Security Headers & Error Handlers
"""

import os
import logging
import secrets
import hmac
from flask import Flask, request, jsonify, session
from werkzeug.exceptions import HTTPException

from app.config import get_config, Config
from app.models.database import init_database, close_db, DEFAULT_DB_PATH


def configure_logging(app):
    """
    Configures centralized application logging based on config LOG_LEVEL.
    """
    log_level_name = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    if not app.logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(name)s (%(module)s): %(message)s'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)

    app.logger.setLevel(log_level)


def register_error_handlers(app):
    """
    Registers consistent JSON error handlers for API requests while allowing
    standard HTTP responses or SPA routing for frontend requests.
    """
    @app.errorhandler(400)
    def handle_bad_request(e):
        if request.path.startswith('/api/'):
            description = getattr(e, 'description', 'Bad Request')
            return jsonify({
                "success": False,
                "error": description
            }), 400
        return e

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "error": f"API endpoint '{request.path}' not found."
            }), 404
        return e

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "error": f"Method {request.method} not allowed for '{request.path}'."
            }), 405
        return e

    @app.errorhandler(500)
    def handle_internal_server_error(e):
        app.logger.error(f"Internal server error on {request.path}: {str(e)}", exc_info=True)
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "error": "An internal server error occurred."
            }), 500
        return e

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "error": e.description
            }), e.code
        return e


def create_app(test_config=None):
    """
    Creates and configures the Flask application.
    Supports modular configuration classes, test configuration overrides,
    lifecycle teardown hooks, security headers, and blueprint registration.
    """
    app = Flask(__name__, static_folder=None)

    # 1. Load Environment Configuration
    config_cls = get_config()
    app.config.from_object(config_cls)

    # 2. Apply Test Configuration Overrides if provided
    if test_config:
        app.config.update(test_config)
        # When test_config is provided without explicit CSRF_ENABLED, default to False for test harness compatibility
        if 'CSRF_ENABLED' not in test_config:
            app.config['CSRF_ENABLED'] = False

    # Ensure secret_key attribute matches app.config['SECRET_KEY']
    app.secret_key = app.config['SECRET_KEY']

    # 3. Setup Logging
    configure_logging(app)

    # 4. Register Database Teardown Handler
    app.teardown_appcontext(close_db)

    # 5. CSRF Protection Middleware
    @app.before_request
    def csrf_protect():
        # Ensure session has a csrf_token initialized
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)

        # Check if CSRF enforcement is enabled
        if not app.config.get('CSRF_ENABLED', True):
            return None

        # Safe HTTP methods are exempt
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return None

        # Exemption for initial login and demo role switch endpoints
        if request.path in ('/api/auth/login', '/api/auth/switch-role'):
            return None

        # Only cookie-authenticated sessions are subject to CSRF validation
        if 'user_id' not in session:
            return None

        # Extract client token from headers or request payload
        client_token = (
            request.headers.get('X-CSRF-Token') or
            request.headers.get('X-CSRFToken') or
            request.headers.get('X-XSRF-TOKEN')
        )
        if not client_token and request.is_json:
            body = request.get_json(silent=True) or {}
            client_token = body.get('csrf_token')
        elif not client_token and request.form:
            client_token = request.form.get('csrf_token')

        server_token = session.get('csrf_token')

        # Compare using constant-time comparison
        if not client_token or not server_token or not hmac.compare_digest(str(client_token), str(server_token)):
            return jsonify({
                "success": False,
                "error": "CSRF token missing or invalid."
            }), 403

    # 6. Baseline HTTP Security Headers & CSRF Cookie Delivery
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Set readable CSRF cookie and response header if CSRF token exists
        csrf_tok = session.get('csrf_token')
        if csrf_tok:
            response.headers['X-CSRF-Token'] = csrf_tok
            secure_cookie = app.config.get('SESSION_COOKIE_SECURE', False)
            response.set_cookie(
                'csrf_token',
                csrf_tok,
                httponly=False,
                samesite=app.config.get('SESSION_COOKIE_SAMESITE', 'Lax'),
                secure=secure_cookie,
                path='/'
            )

        return response

    # 7. Initialize Database with schema & seeds
    db_target = app.config.get('DATABASE_URL') or app.config.get('DB_PATH', DEFAULT_DB_PATH)
    init_database(db_target)

    # 8. Register Global Error Handlers
    register_error_handlers(app)

    # 9. Register Blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.order_routes import order_bp
    from app.routes.inspection_routes import inspection_bp
    from app.routes.agreement_routes import agreement_bp
    from app.routes.plant_routes import plant_bp
    from app.routes.invoice_routes import invoice_bp
    from app.routes.payment_routes import payment_bp
    from app.routes.ledger_routes import ledger_bp
    from app.routes.nursery_routes import nursery_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.static_routes import static_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(inspection_bp)
    app.register_blueprint(agreement_bp)
    app.register_blueprint(plant_bp)
    app.register_blueprint(invoice_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(nursery_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(static_bp)

    return app
