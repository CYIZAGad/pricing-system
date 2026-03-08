"""
Tests for the Authentication Blueprint (/api/v1/auth)
Covers: login, logout, verify, register
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import (
    FakeRow, ADMIN_USER_ID, DEPOT_USER_ID, TENANT_ID, TENANT_DB_NAME,
)


# =====================================================================
# LOGIN
# =====================================================================

class TestLogin:
    """POST /api/v1/auth/login"""

    URL = '/api/v1/auth/login'

    # -- Successful login --------------------------------------------------

    def test_login_success_admin(self, client, mock_central_db, fake_admin_user):
        """Admin user can log in with correct credentials."""
        # First call => user lookup, second call => UPDATE last_login, third => INSERT session
        mock_central_db.execute.return_value.fetchone.side_effect = [
            fake_admin_user,  # user query
            None,             # update last_login
            None,             # insert session
        ]

        resp = client.post(self.URL, json={
            'email': 'admin@test.com',
            'password': 'Admin123',
        })

        assert resp.status_code == 200
        data = resp.get_json()
        assert 'token' in data
        assert data['user']['email'] == 'admin@test.com'
        assert data['user']['role'] == 'admin'

    def test_login_success_depot(self, client, mock_central_db, fake_depot_user, fake_tenant):
        """Depot user can log in and receives tenant info."""
        # user lookup ➜ update last_login ➜ insert session ➜ tenant lookup
        mock_central_db.execute.return_value.fetchone.side_effect = [
            fake_depot_user,
            None,
            None,
            fake_tenant,
        ]

        resp = client.post(self.URL, json={
            'email': 'depot@test.com',
            'password': 'Depot123',
        })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['user']['role'] == 'depot'
        assert data['tenant'] is not None or 'tenant' in data

    # -- Missing fields ----------------------------------------------------

    def test_login_missing_email(self, client, mock_central_db):
        resp = client.post(self.URL, json={'password': 'whatever'})
        assert resp.status_code == 400

    def test_login_missing_password(self, client, mock_central_db):
        resp = client.post(self.URL, json={'email': 'x@y.com'})
        assert resp.status_code == 400

    def test_login_empty_body(self, client, mock_central_db):
        resp = client.post(self.URL, json={})
        assert resp.status_code == 400

    # -- Invalid credentials -----------------------------------------------

    def test_login_user_not_found(self, client, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = None

        resp = client.post(self.URL, json={
            'email': 'nobody@test.com',
            'password': 'Password1',
        })
        assert resp.status_code == 401

    def test_login_wrong_password(self, client, mock_central_db, fake_admin_user):
        mock_central_db.execute.return_value.fetchone.return_value = fake_admin_user

        resp = client.post(self.URL, json={
            'email': 'admin@test.com',
            'password': 'WrongPass1',
        })
        assert resp.status_code == 401

    def test_login_inactive_user(self, client, mock_central_db, fake_admin_user):
        fake_admin_user.is_active = False
        mock_central_db.execute.return_value.fetchone.return_value = fake_admin_user

        resp = client.post(self.URL, json={
            'email': 'admin@test.com',
            'password': 'Admin123',
        })
        assert resp.status_code == 403


# =====================================================================
# VERIFY SESSION
# =====================================================================

class TestVerify:
    """GET /api/v1/auth/verify"""

    URL = '/api/v1/auth/verify'

    def test_verify_no_session(self, client, mock_central_db):
        """Returns 401 when there is no Flask session."""
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_verify_valid_session(self, client, app, mock_central_db, fake_session_row):
        """Returns 200 when session cookie exists and is valid."""
        mock_central_db.execute.return_value.fetchone.return_value = fake_session_row

        with client.session_transaction() as sess:
            sess['session_token'] = 'valid-token'
            sess['user_id'] = ADMIN_USER_ID
            sess['role'] = 'admin'

        resp = client.get(self.URL)
        assert resp.status_code == 200
        assert resp.get_json()['valid'] is True

    def test_verify_expired_session(self, client, app, mock_central_db):
        """Returns 401 when session has expired."""
        expired = FakeRow(
            user_id=uuid.UUID(ADMIN_USER_ID),
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        mock_central_db.execute.return_value.fetchone.return_value = expired

        with client.session_transaction() as sess:
            sess['session_token'] = 'expired-token'
            sess['user_id'] = ADMIN_USER_ID

        resp = client.get(self.URL)
        assert resp.status_code == 401


# =====================================================================
# LOGOUT
# =====================================================================

class TestLogout:
    """POST /api/v1/auth/logout"""

    URL = '/api/v1/auth/logout'

    def test_logout_clears_session(self, client, mock_central_db):
        """Logout should return 200 and clear the session."""
        with client.session_transaction() as sess:
            sess['session_token'] = 'some-token'
            sess['user_id'] = ADMIN_USER_ID

        resp = client.post(self.URL)
        assert resp.status_code == 200
        assert resp.get_json()['message'] == 'Logged out successfully'

    def test_logout_without_session(self, client, mock_central_db):
        """Logout still returns 200 even without an active session."""
        resp = client.post(self.URL)
        assert resp.status_code == 200


# =====================================================================
# REGISTER (admin-only)
# =====================================================================

class TestRegister:
    """POST /api/v1/auth/register"""

    URL = '/api/v1/auth/register'

    def test_register_requires_auth(self, client, mock_central_db):
        """Returns 401 without any authentication."""
        resp = client.post(self.URL, json={
            'email': 'new@test.com',
            'password': 'Newuser1',
            'role': 'depot',
        })
        assert resp.status_code == 401

    def test_register_requires_admin_role(self, client, depot_headers, mock_central_db):
        """Depot users cannot register new users."""
        resp = client.post(self.URL, json={
            'email': 'new@test.com',
            'password': 'Newuser1',
            'role': 'depot',
        }, headers=depot_headers)
        assert resp.status_code == 403

    def test_register_missing_fields(self, client, admin_headers, mock_central_db):
        """Returns 400 when required fields missing."""
        resp = client.post(self.URL, json={
            'email': 'new@test.com',
        }, headers=admin_headers)
        assert resp.status_code == 400

    def test_register_weak_password(self, client, admin_headers, mock_central_db):
        """Returns 400 when password is too short / weak."""
        resp = client.post(self.URL, json={
            'email': 'new@test.com',
            'password': 'abc',
            'role': 'depot',
        }, headers=admin_headers)
        assert resp.status_code == 400

    def test_register_invalid_role(self, client, admin_headers, mock_central_db):
        """Returns 400 when an unsupported role is passed."""
        resp = client.post(self.URL, json={
            'email': 'new@test.com',
            'password': 'Valid1pw',
            'role': 'superadmin',
        }, headers=admin_headers)
        assert resp.status_code == 400

    def test_register_duplicate_email(self, client, admin_headers, mock_central_db, fake_admin_user):
        """Returns 409 when an email already exists."""
        mock_central_db.execute.return_value.fetchone.return_value = fake_admin_user

        resp = client.post(self.URL, json={
            'email': 'admin@test.com',
            'password': 'Valid1pw',
            'role': 'depot',
        }, headers=admin_headers)
        assert resp.status_code == 409

    def test_register_success(self, client, admin_headers, mock_central_db):
        """Admin can register a new user."""
        new_user = FakeRow(
            id=uuid.uuid4(),
            email='new@test.com',
            full_name='New User',
            role='depot',
            tenant_id=None,
        )
        # First call => duplicate check (None), second => INSERT RETURNING
        mock_central_db.execute.return_value.fetchone.side_effect = [
            None,      # no existing user
            new_user,  # newly created user
        ]

        resp = client.post(self.URL, json={
            'email': 'new@test.com',
            'password': 'Valid1pw',
            'role': 'depot',
            'full_name': 'New User',
        }, headers=admin_headers)
        assert resp.status_code == 201
        assert resp.get_json()['user']['email'] == 'new@test.com'


# =====================================================================
# PASSWORD VALIDATION UNIT TESTS
# =====================================================================

class TestPasswordValidation:
    """Direct unit tests for auth._validate_password"""

    def _validate(self, pw):
        from app.blueprints.auth import _validate_password
        return _validate_password(pw)

    def test_too_short(self):
        ok, _ = self._validate('Ab1')
        assert not ok

    def test_no_uppercase(self):
        ok, _ = self._validate('abcdefg1')
        assert not ok

    def test_no_lowercase(self):
        ok, _ = self._validate('ABCDEFG1')
        assert not ok

    def test_no_digit(self):
        ok, _ = self._validate('Abcdefgh')
        assert not ok

    def test_valid(self):
        ok, _ = self._validate('StrongP1')
        assert ok


# =====================================================================
# RATE LIMITING UNIT TESTS
# =====================================================================

class TestRateLimiting:
    """Direct unit tests for auth rate-limiting helpers."""

    def test_not_limited_by_default(self):
        from app.blueprints.auth import _is_rate_limited
        assert not _is_rate_limited('192.168.99.1')

    def test_limited_after_max_attempts(self):
        from app.blueprints.auth import _record_attempt, _is_rate_limited, _LOGIN_MAX
        ip = '10.99.99.99'
        for _ in range(_LOGIN_MAX):
            _record_attempt(ip)
        assert _is_rate_limited(ip)
