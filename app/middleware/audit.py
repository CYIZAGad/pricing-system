"""
Audit logging middleware
Logs all API requests to audit_logs table
"""

from flask import request
from app.database.central_db import CentralDB
from sqlalchemy import text
import logging
import json

logger = logging.getLogger(__name__)


def audit_middleware():
    """Middleware to log API requests - called before each request"""
    # Skip audit for health checks and static files
    if request.path.startswith('/static') or request.path == '/health':
        return
    
    # Store user info in request context for after_request
    request.audit_user_id = None
    request.audit_tenant_id = None
    
    try:
        from app.utils.auth import get_token_from_request, verify_token
        token = get_token_from_request()
        if token:
            payload = verify_token(token)
            if payload:
                request.audit_user_id = payload.get('user_id')
                request.audit_tenant_id = payload.get('tenant_id')
    except:
        pass


def log_request(response):
    """Log request after response is generated"""
    # Skip audit for health checks and static files
    if request.path.startswith('/static') or request.path == '/health':
        return response
    
    try:
        session = CentralDB.get_session()
        session.execute(text("""
            INSERT INTO audit_logs (user_id, tenant_id, action, resource_type, 
                ip_address, user_agent, details)
            VALUES (:user_id, :tenant_id, :action, :resource_type, 
                :ip_address, :user_agent, CAST(:details AS jsonb))
        """), {
            'user_id': getattr(request, 'audit_user_id', None),
            'tenant_id': getattr(request, 'audit_tenant_id', None),
            'action': f"{request.method} {request.path}",
            'resource_type': 'api_request',
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent'),
            'details': json.dumps({
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code
            })
        })
        session.commit()
        session.close()
    except Exception as e:
        logger.error(f"Audit logging failed: {e}")
        try:
            if session:
                session.rollback()
                session.close()
        except:
            pass
    
    return response
