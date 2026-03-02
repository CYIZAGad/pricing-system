"""
Authentication utilities - JWT and password hashing
"""

import jwt
import bcrypt
from datetime import datetime, timedelta
from flask import current_app, session as flask_session
from functools import wraps
from flask import request, jsonify
from app.database.central_db import CentralDB
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')


def verify_password(password, hashed):
    """Verify password against hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def generate_token(user_id, email, role, tenant_id=None):
    """Generate JWT access token"""
    payload = {
        'user_id': str(user_id),
        'email': email,
        'role': role,
        'tenant_id': str(tenant_id) if tenant_id else None,
        'exp': datetime.utcnow() + timedelta(seconds=current_app.config['JWT_ACCESS_TOKEN_EXPIRES']),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')


def verify_token(token):
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_token_from_request():
    """Extract token from request header"""
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    return None


def require_auth(f):
    """Decorator to require authentication - checks JWT token or Flask session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First try JWT token from Authorization header
        token = get_token_from_request()
        if token:
            payload = verify_token(token)
            if payload:
                request.current_user = payload
                return f(*args, **kwargs)
        
        # Fallback to Flask session (for API calls with credentials: 'include')
        session_token = flask_session.get('session_token')
        user_id = flask_session.get('user_id')
        user_role = flask_session.get('role')
        tenant_id = flask_session.get('tenant_id')
        
        if session_token and user_id:
            # Verify session exists in database and is not expired
            try:
                db_session = CentralDB.get_session()
                result = db_session.execute(
                    text("""
                        SELECT user_id, expires_at 
                        FROM user_sessions 
                        WHERE session_token = :token AND user_id = :user_id
                    """),
                    {'token': session_token, 'user_id': user_id}
                )
                session_data = result.fetchone()
                db_session.close()
                
                if session_data and session_data.expires_at >= datetime.utcnow():
                    # Valid session - attach user info to request
                    request.current_user = {
                        'user_id': user_id,
                        'role': user_role,
                        'tenant_id': tenant_id
                    }
                    return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Session verification error: {e}")
        
        # No valid authentication found
        return jsonify({'error': 'Authentication required'}), 401
    
    return decorated_function


def require_role(*allowed_roles):
    """Decorator to require specific role(s)"""
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated_function(*args, **kwargs):
            user_role = request.current_user.get('role')
            if user_role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
