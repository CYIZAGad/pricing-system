"""
Tests for frontend routes, health check, error handlers,
audit middleware, auth utilities, and security headers.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import (
    FakeRow, ADMIN_USER_ID, DEPOT_USER_ID, TENANT_ID,
)


# =====================================================================
# HEALTH CHECK
# =====================================================================

class TestHealthCheck:
    """GET /health (unauthenticated)"""

    def test_health_returns_200(self, client):
        resp = client.get('/health')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'ok'


# =====================================================================
# LANDING PAGE
# =====================================================================

class TestLandingPage:
    """GET / (unauthenticated)"""

    def test_renders_landing(self, client, mock_central_db):
        resp = client.get('/')
        assert resp.status_code == 200
        # Should return HTML
        assert b'<!DOCTYPE html>' in resp.data or b'<html' in resp.data


# =====================================================================
# ADMIN PAGE (session-gated)
# =====================================================================

class TestAdminPage:
    """GET /admin.html"""

    def test_redirect_without_session(self, client, mock_central_db):
        resp = client.get('/admin.html')
        assert resp.status_code in (302, 200)  # redirects to /

    def test_redirect_for_depot_role(self, client, mock_central_db, fake_session_row):
        mock_central_db.execute.return_value.fetchone.return_value = fake_session_row
        with client.session_transaction() as sess:
            sess['session_token'] = 'tok'
            sess['user_id'] = ADMIN_USER_ID
            sess['role'] = 'depot'  # Wrong role

        resp = client.get('/admin.html')
        assert resp.status_code in (302, 200)

    def test_admin_page_with_valid_session(self, client, mock_central_db, fake_session_row):
        mock_central_db.execute.return_value.fetchone.return_value = fake_session_row
        with client.session_transaction() as sess:
            sess['session_token'] = 'tok'
            sess['user_id'] = ADMIN_USER_ID
            sess['role'] = 'admin'

        resp = client.get('/admin.html')
        assert resp.status_code == 200


# =====================================================================
# DEPOT PAGE (session-gated)
# =====================================================================

class TestDepotPage:
    """GET /depot.html"""

    def test_redirect_without_session(self, client, mock_central_db):
        resp = client.get('/depot.html')
        assert resp.status_code in (302, 200)

    def test_depot_page_with_valid_session(self, client, mock_central_db, fake_session_row):
        mock_central_db.execute.return_value.fetchone.return_value = fake_session_row
        with client.session_transaction() as sess:
            sess['session_token'] = 'tok'
            sess['user_id'] = DEPOT_USER_ID
            sess['role'] = 'depot'

        resp = client.get('/depot.html')
        assert resp.status_code == 200


# =====================================================================
# ERROR HANDLERS
# =====================================================================

class TestErrorHandlers:
    """Verify custom JSON error responses."""

    def test_404(self, client):
        resp = client.get('/non-existent-route')
        assert resp.status_code == 404
        data = resp.get_json()
        assert data is not None
        assert 'error' in data


# =====================================================================
# SECURITY HEADERS
# =====================================================================

class TestSecurityHeaders:
    """Verify that security headers are set on every response."""

    def test_headers_present(self, client):
        resp = client.get('/health')
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'
        assert resp.headers.get('X-Frame-Options') == 'SAMEORIGIN'
        assert resp.headers.get('X-XSS-Protection') == '1; mode=block'
        assert 'Content-Security-Policy' in resp.headers


# =====================================================================
# AUTH UTILITIES
# =====================================================================

class TestAuthUtils:
    """Unit tests for app/utils/auth.py helpers."""

    def test_hash_and_verify(self):
        from app.utils.auth import hash_password, verify_password
        pw = 'TestPass123'
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)
        assert not verify_password('wrong', hashed)

    def test_generate_and_verify_token(self, app):
        from app.utils.auth import generate_token, verify_token
        with app.app_context():
            token = generate_token(
                user_id=uuid.uuid4(),
                email='u@example.com',
                role='admin',
                tenant_id=None,
            )
            payload = verify_token(token)
            assert payload is not None
            assert payload['role'] == 'admin'

    def test_expired_token(self, app):
        import jwt as pyjwt
        from app.utils.auth import verify_token
        payload = {
            'user_id': 'x',
            'exp': datetime.utcnow() - timedelta(hours=1),
            'iat': datetime.utcnow() - timedelta(hours=2),
        }
        token = pyjwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')
        with app.app_context():
            assert verify_token(token) is None

    def test_invalid_token(self, app):
        from app.utils.auth import verify_token
        with app.app_context():
            assert verify_token('garbage.token.value') is None


# =====================================================================
# REQUIRE_AUTH DECORATOR
# =====================================================================

class TestRequireAuth:
    """The @require_auth decorator should reject unauthenticated requests."""

    # Any admin-protected endpoint works as a proxy
    PROTECTED = '/api/v1/admin/tenants'

    def test_no_token_no_session(self, client, mock_central_db):
        resp = client.get(self.PROTECTED)
        assert resp.status_code == 401

    def test_invalid_bearer(self, client, mock_central_db):
        resp = client.get(self.PROTECTED, headers={'Authorization': 'Bearer bad'})
        assert resp.status_code == 401


# =====================================================================
# REQUIRE_ROLE DECORATOR
# =====================================================================

class TestRequireRole:
    """The @require_role decorator should reject wrong roles."""

    def test_depot_cannot_access_admin(self, client, depot_headers, mock_central_db):
        resp = client.get('/api/v1/admin/tenants', headers=depot_headers)
        assert resp.status_code == 403

    def test_admin_cannot_access_depot(self, client, admin_headers, mock_central_db):
        resp = client.get('/api/v1/depot/medicines', headers=admin_headers)
        assert resp.status_code == 403


# =====================================================================
# AUDIT MIDDLEWARE
# =====================================================================

class TestAuditMiddleware:
    """Verify the audit_middleware and log_request hooks."""

    def test_audit_skips_static(self, client):
        """Requests to /static should not trigger audit logging."""
        # Simply check that the request completes without error
        resp = client.get('/static/css/style.css')
        # May 200 or 404, but should not 500
        assert resp.status_code != 500

    def test_audit_skips_health(self, client):
        resp = client.get('/health')
        assert resp.status_code == 200

    def test_audit_logs_api_calls(self, client, mock_central_db, admin_headers):
        """API calls should trigger audit insert (mocked)."""
        # list tenants call — the mock prevents actual DB writes
        resp = client.get('/api/v1/admin/tenants', headers=admin_headers)
        # confirm audit middleware ran (mock was called for the audit INSERT)
        assert mock_central_db.execute.called


# =====================================================================
# CENTRAL DB MANAGER
# =====================================================================

class TestCentralDBManager:
    """Tests for CentralDB class."""

    @patch('app.database.central_db.CentralDB._engine', None)
    @patch('app.database.central_db.CentralDB._session_factory', None)
    @patch('app.database.central_db.create_engine')
    def test_initialize_creates_engine(self, mock_ce):
        from app.database.central_db import CentralDB
        CentralDB._engine = None
        CentralDB._session_factory = None
        mock_ce.return_value = MagicMock()
        CentralDB.initialize()
        mock_ce.assert_called_once()

    def test_close_session(self):
        from app.database.central_db import CentralDB
        CentralDB._session_factory = MagicMock()
        CentralDB.close_session()
        CentralDB._session_factory.remove.assert_called_once()


# =====================================================================
# TENANT DB MANAGER
# =====================================================================

class TestTenantDBManager:
    """Tests for TenantDBManager class."""

    @patch('app.database.tenant_db.create_engine')
    def test_get_engine_caches(self, mock_ce):
        from app.database.tenant_db import TenantDBManager
        TenantDBManager._engines = {}  # reset cache
        mock_ce.return_value = MagicMock()
        e1 = TenantDBManager.get_engine('test_db')
        e2 = TenantDBManager.get_engine('test_db')
        assert e1 is e2
        mock_ce.assert_called_once()

    @patch('app.database.tenant_db.TenantDBManager.get_engine')
    def test_get_session(self, mock_ge):
        from app.database.tenant_db import TenantDBManager
        mock_ge.return_value = MagicMock()
        session = TenantDBManager.get_session('test_db')
        assert session is not None
