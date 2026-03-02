"""
Authentication Blueprint
Handles login, logout, and user authentication
"""

from flask import Blueprint, request, jsonify, session as flask_session
from app.database.central_db import CentralDB
from app.utils.auth import hash_password, verify_password, generate_token, require_role
from sqlalchemy import text
from datetime import datetime, timedelta
import logging
import secrets
import re
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# ---------- Simple in-memory rate limiter for login ----------
_login_attempts = defaultdict(list)   # ip -> [timestamps]
_LOGIN_WINDOW = 300   # 5 minutes
_LOGIN_MAX = 10       # max attempts per window


def _is_rate_limited(ip):
    """Return True if this IP has exceeded the login rate limit."""
    now = time.time()
    attempts = _login_attempts[ip]
    # Prune old entries
    _login_attempts[ip] = [t for t in attempts if now - t < _LOGIN_WINDOW]
    return len(_login_attempts[ip]) >= _LOGIN_MAX


def _record_attempt(ip):
    _login_attempts[ip].append(time.time())


# ---------- Password strength validator ----------
_PASSWORD_MIN_LENGTH = 8


def _validate_password(password):
    """Return (ok: bool, message: str). Requires >= 8 chars, 1 upper, 1 lower, 1 digit."""
    if len(password) < _PASSWORD_MIN_LENGTH:
        return False, f'Password must be at least {_PASSWORD_MIN_LENGTH} characters'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter'
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one digit'
    return True, ''


@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        # Rate limiting
        client_ip = request.remote_addr
        if _is_rate_limited(client_ip):
            return jsonify({'error': 'Too many login attempts. Please try again in a few minutes.'}), 429
        _record_attempt(client_ip)

        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        session = CentralDB.get_session()
        
        # Get user from database
        result = session.execute(
            text("""
                SELECT id, email, password_hash, full_name, role, tenant_id, is_active
                FROM users
                WHERE email = :email
            """),
            {'email': email}
        )
        user = result.fetchone()
        
        if not user:
            session.close()
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check if user is active
        if not user.is_active:
            session.close()
            return jsonify({'error': 'Account is inactive'}), 403
        
        # Verify password
        if not verify_password(password, user.password_hash):
            session.close()
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Update last login
        session.execute(
            text("UPDATE users SET last_login = :now WHERE id = :user_id"),
            {'now': datetime.utcnow(), 'user_id': user.id}
        )
        
        # Generate session token
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Create session in database
        session.execute(
            text("""
                INSERT INTO user_sessions (user_id, session_token, ip_address, user_agent, expires_at)
                VALUES (:user_id, :session_token, :ip_address, :user_agent, :expires_at)
            """),
            {
                'user_id': user.id,
                'session_token': session_token,
                'ip_address': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', ''),
                'expires_at': expires_at
            }
        )
        
        session.commit()
        session.close()
        
        # Store session in Flask session (server-side, secure cookie)
        flask_session['user_id'] = str(user.id)
        flask_session['session_token'] = session_token
        flask_session['role'] = user.role
        flask_session['tenant_id'] = str(user.tenant_id) if user.tenant_id else None
        flask_session.permanent = True
        
        # Generate JWT token for API calls
        token = generate_token(user.id, user.email, user.role, user.tenant_id)
        
        # Get tenant info if exists
        tenant_info = None
        if user.tenant_id:
            db_session = CentralDB.get_session()
            tenant_result = db_session.execute(
                text("SELECT id, business_name, database_name FROM tenants WHERE id = :tenant_id"),
                {'tenant_id': user.tenant_id}
            )
            tenant = tenant_result.fetchone()
            if tenant:
                tenant_info = {
                    'id': str(tenant.id),
                    'business_name': tenant.business_name,
                    'database_name': tenant.database_name
                }
            db_session.close()
        
        return jsonify({
            'token': token,
            'session_id': session_token,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'tenant_id': str(user.tenant_id) if user.tenant_id else None
            },
            'tenant': tenant_info
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed', 'message': str(e)}), 500


@auth_bp.route('/verify', methods=['GET'])
def verify_token():
    """Verify if session is still valid"""
    try:
        session_token = flask_session.get('session_token')
        user_id = flask_session.get('user_id')
        
        if not session_token or not user_id:
            return jsonify({'error': 'No active session'}), 401
        
        # Verify session exists in database and is not expired
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
        
        if not session_data:
            # Session doesn't exist - clear Flask session
            flask_session.clear()
            return jsonify({'error': 'Session not found'}), 401
        
        # Check if session expired
        if session_data.expires_at < datetime.utcnow():
            # Delete expired session
            db_session = CentralDB.get_session()
            db_session.execute(
                text("DELETE FROM user_sessions WHERE session_token = :token"),
                {'token': session_token}
            )
            db_session.commit()
            db_session.close()
            flask_session.clear()
            return jsonify({'error': 'Session expired'}), 401
        
        # Update last activity
        db_session = CentralDB.get_session()
        db_session.execute(
            text("UPDATE user_sessions SET last_activity = :now WHERE session_token = :token"),
            {'now': datetime.utcnow(), 'token': session_token}
        )
        db_session.commit()
        db_session.close()
        
        return jsonify({'valid': True, 'user_id': user_id}), 200
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        flask_session.clear()
        return jsonify({'error': 'Session verification failed'}), 401


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """User logout endpoint - destroys server-side session"""
    try:
        session_token = flask_session.get('session_token')
        user_id = flask_session.get('user_id')
        
        if session_token:
            # Delete session from database
            db_session = CentralDB.get_session()
            db_session.execute(
                text("DELETE FROM user_sessions WHERE session_token = :token"),
                {'token': session_token}
            )
            db_session.commit()
            db_session.close()
        
        # Clear Flask session
        flask_session.clear()
        
        return jsonify({'message': 'Logged out successfully'}), 200
    except Exception as e:
        logger.error(f"Logout error: {e}")
        # Clear session even if database deletion fails
        flask_session.clear()
        return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/register', methods=['POST'])
@require_role('admin')
def register():
    """User registration endpoint (admin only — requires authentication)"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')
        full_name = data.get('full_name')
        phone = data.get('phone')
        tenant_id = data.get('tenant_id')
        
        if not email or not password or not role:
            return jsonify({'error': 'Email, password, and role are required'}), 400
        
        # Validate password strength
        pw_ok, pw_msg = _validate_password(password)
        if not pw_ok:
            return jsonify({'error': pw_msg}), 400
        
        # Validate role (only admin and depot allowed)
        valid_roles = ['admin', 'depot']
        if role not in valid_roles:
            return jsonify({'error': 'Invalid role. Only "admin" and "depot" are allowed'}), 400
        
        session = CentralDB.get_session()
        
        # Check if user exists
        existing = session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {'email': email}
        ).fetchone()
        
        if existing:
            session.close()
            return jsonify({'error': 'User already exists'}), 409
        
        # Hash password
        password_hash = hash_password(password)
        
        # Insert user
        result = session.execute(
            text("""
                INSERT INTO users (email, password_hash, full_name, phone, role, tenant_id, is_active, email_verified)
                VALUES (:email, :password_hash, :full_name, :phone, :role, :tenant_id, TRUE, TRUE)
                RETURNING id, email, full_name, role, tenant_id
            """),
            {
                'email': email,
                'password_hash': password_hash,
                'full_name': full_name,
                'phone': phone,
                'role': role,
                'tenant_id': tenant_id
            }
        )
        user = result.fetchone()
        session.commit()
        session.close()
        
        return jsonify({
            'message': 'User created successfully',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed', 'message': 'An internal error occurred'}), 500
