"""
Pharmacy Pricing System - Flask Application Factory
Multi-tenant SaaS application for medicine price distribution
"""

from flask import Flask
from flask_cors import CORS
from datetime import timedelta
from config import Config


def create_app(config_class=Config):
    """Application factory pattern"""
    import os
    # Get the base directory (project root) - one level up from app/
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    
    # Verify directories exist
    if not os.path.exists(template_dir):
        raise FileNotFoundError(f"Templates directory not found: {template_dir}")
    if not os.path.exists(static_dir):
        raise FileNotFoundError(f"Static directory not found: {static_dir}")
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(config_class)
    
    # Configure session
    is_production = config_class.FLASK_ENV == 'production'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = is_production  # True in production (HTTPS)
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Enable CORS — restrict origins in production
    cors_origins = config_class.CORS_ORIGINS
    if cors_origins != '*':
        cors_origins = [o.strip() for o in cors_origins.split(',')]
    CORS(app, supports_credentials=True, origins=cors_origins)
    
    # Register frontend routes
    from app.routes import index, admin, depot, static_files
    app.add_url_rule('/', 'index', index)
    app.add_url_rule('/admin.html', 'admin', admin)
    app.add_url_rule('/depot.html', 'depot', depot)
    app.add_url_rule('/static/<path:filename>', 'static_files', static_files)
    
    # Register blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.depot import depot_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/v1/admin')
    app.register_blueprint(depot_bp, url_prefix='/api/v1/depot')
    
    # Register error handlers
    from app.errors import register_error_handlers
    register_error_handlers(app)
    
    # Register middleware
    from app.middleware.audit import audit_middleware, log_request
    app.before_request(audit_middleware)
    app.after_request(log_request)
    
    # --- Security headers (applied to every response) ---
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if is_production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        # Content-Security-Policy — allow inline styles/scripts the app already uses
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'"
        )
        return response
    
    # --- Unauthenticated health check for load balancers ---
    @app.route('/health')
    def health_check():
        from flask import jsonify as _jsonify
        return _jsonify({'status': 'ok'}), 200
    
    return app
