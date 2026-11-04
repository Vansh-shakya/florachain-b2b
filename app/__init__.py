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

from app.config import get_config, Config, ProductionConfig
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
    is_vercel = os.environ.get('VERCEL') == '1' or bool(os.environ.get('VERCEL_ENV'))
    is_production = (
        (isinstance(config_cls, type) and issubclass(config_cls, ProductionConfig))
        or config_cls == ProductionConfig
        or is_vercel
    )

    db_target = app.config.get('DATABASE_URL')

    if (is_production or is_vercel) and not db_target:
        app.config['DATABASE_MISCONFIGURED'] = True
        app.logger.critical(
            "FloraChain B2B: DATABASE_URL is not configured in production / Vercel. "
            "SQLite is disabled on Vercel's read-only serverless filesystem. "
            "Please configure DATABASE_URL in Vercel Project Settings."
        )

        @app.before_request
        def handle_missing_production_database():
            if request.path == '/api/health':
                return jsonify({
                    "status": "misconfigured",
                    "service": "FloraChain B2B Backend Engine",
                    "error": "DATABASE_URL is not configured in production. A hosted PostgreSQL database is required for Vercel deployment.",
                    "action_required": "Set DATABASE_URL in Vercel Project Settings > Environment Variables."
                }), 503

            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "Production Database Not Configured: DATABASE_URL environment variable is missing. Please configure your PostgreSQL connection in Vercel."
                }), 503

            return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>FloraChain B2B — Database Configuration Required</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; background: #f4f6f3; color: #1c2e1b; margin: 0; padding: 2rem; display: flex; align-items: center; justify-content: center; min-height: 90vh; }
    .card { background: white; border: 1px solid #d4dfd2; border-top: 6px solid #063B00; border-radius: 8px; max-width: 620px; padding: 2.5rem; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }
    h1 { color: #063B00; margin-top: 0; font-size: 1.5rem; display: flex; align-items: center; gap: 0.5rem; }
    p { line-height: 1.6; color: #374151; }
    ol { padding-left: 1.25rem; line-height: 1.8; color: #374151; }
    code { background: #f3f4f6; padding: 0.2rem 0.4rem; border-radius: 4px; font-size: 0.9em; color: #063B00; font-weight: 600; }
    .badge { display: inline-block; background: #fef3c7; color: #92400e; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; margin-bottom: 1rem; }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">⚙️ Production Setup Required</div>
    <h1>🌿 FloraChain B2B — Database Setup Needed</h1>
    <p>Your application is successfully running on Vercel, but the <strong>hosted PostgreSQL database</strong> has not been connected yet.</p>
    <p>Because Vercel serverless functions run on a secure, read-only filesystem, SQLite is disabled in production to protect against data loss.</p>
    <h3>To activate the platform:</h3>
    <ol>
      <li>Create a free PostgreSQL database at <strong>Neon.tech</strong> or <strong>Supabase</strong>.</li>
      <li>Copy your connection string (e.g. <code>postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require</code>).</li>
      <li>Open your <strong>Vercel Dashboard</strong> &rarr; <strong>Settings</strong> &rarr; <strong>Environment Variables</strong>.</li>
      <li>Add <code>DATABASE_URL</code> and paste your connection string.</li>
      <li>Redeploy the project in Vercel.</li>
    </ol>
  </div>
</body>
</html>""", 503
    else:
        if not db_target:
            db_target = app.config.get('DB_PATH', DEFAULT_DB_PATH)
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
