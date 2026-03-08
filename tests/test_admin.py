"""
Tests for the Admin Blueprint (/api/v1/admin)
Covers: tenant CRUD, user CRUD, system health, admin profile, password change
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import (
    FakeRow, ADMIN_USER_ID, DEPOT_USER_ID, TENANT_ID, TENANT_DB_NAME,
)


# =====================================================================
# CREATE TENANT
# =====================================================================

class TestCreateTenant:
    """POST /api/v1/admin/tenant"""

    URL = '/api/v1/admin/tenant'

    def test_requires_auth(self, client, mock_central_db):
        resp = client.post(self.URL, json={'business_name': 'X', 'email': 'x@y.com'})
        assert resp.status_code == 401

    def test_requires_admin_role(self, client, depot_headers, mock_central_db):
        resp = client.post(self.URL, json={
            'business_name': 'X', 'email': 'x@y.com',
            'password': 'Test123', 'password_confirm': 'Test123',
        }, headers=depot_headers)
        assert resp.status_code == 403

    def test_missing_business_name(self, client, admin_headers, mock_central_db):
        resp = client.post(self.URL, json={'email': 'x@y.com', 'password': 'Test123', 'password_confirm': 'Test123'},
                           headers=admin_headers)
        assert resp.status_code == 400

    def test_missing_password(self, client, admin_headers, mock_central_db):
        resp = client.post(self.URL, json={'business_name': 'X', 'email': 'x@y.com'},
                           headers=admin_headers)
        assert resp.status_code == 400

    def test_password_mismatch(self, client, admin_headers, mock_central_db):
        resp = client.post(self.URL, json={
            'business_name': 'X', 'email': 'x@y.com',
            'password': 'Test123', 'password_confirm': 'Different1',
        }, headers=admin_headers)
        assert resp.status_code == 400

    def test_duplicate_email(self, client, admin_headers, mock_central_db, fake_tenant):
        mock_central_db.execute.return_value.fetchone.return_value = fake_tenant
        resp = client.post(self.URL, json={
            'business_name': 'Y', 'email': 'depot@test.com',
            'password': 'Test123', 'password_confirm': 'Test123',
        }, headers=admin_headers)
        assert resp.status_code == 409

    @patch('app.blueprints.admin.TenantDatabaseCreator')
    def test_create_success(self, MockCreator, client, admin_headers, mock_central_db):
        """Happy path: creates tenant, database, and user."""
        # No existing email, no existing reg, no existing db name, no existing user
        new_tenant = FakeRow(
            id=uuid.uuid4(), business_name='New Depot', email='new@depot.com',
            database_name='tenant_new_depot', status='active',
            created_at=datetime.utcnow(),
        )
        mock_central_db.execute.return_value.fetchone.side_effect = [
            None,        # email check
            None,        # db name check
            new_tenant,  # INSERT RETURNING tenant
            None,        # user email check
        ]

        creator_inst = MagicMock()
        creator_inst.sanitize_db_name.return_value = 'new_depot'
        creator_inst.create_tenant_database_with_name.return_value = (True, 'tenant_new_depot', None)
        MockCreator.return_value = creator_inst

        resp = client.post(self.URL, json={
            'business_name': 'New Depot',
            'email': 'new@depot.com',
            'password': 'Test123',
            'password_confirm': 'Test123',
        }, headers=admin_headers)

        assert resp.status_code == 201
        data = resp.get_json()
        assert data['tenant']['business_name'] == 'New Depot'
        assert 'user' in data


# =====================================================================
# LIST TENANTS
# =====================================================================

class TestListTenants:
    """GET /api/v1/admin/tenants"""

    URL = '/api/v1/admin/tenants'

    def test_requires_auth(self, client, mock_central_db):
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_returns_list(self, client, admin_headers, mock_central_db, fake_tenant):
        mock_central_db.execute.return_value.fetchall.return_value = [fake_tenant]
        mock_central_db.execute.return_value.scalar.return_value = 1

        resp = client.get(self.URL, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'tenants' in data
        assert 'pagination' in data

    def test_empty_list(self, client, admin_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchall.return_value = []
        mock_central_db.execute.return_value.scalar.return_value = 0

        resp = client.get(self.URL, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.get_json()['tenants'] == []


# =====================================================================
# UPDATE TENANT
# =====================================================================

class TestUpdateTenant:
    """PUT /api/v1/admin/tenant/<id>"""

    def _url(self, tid=TENANT_ID):
        return f'/api/v1/admin/tenant/{tid}'

    def test_requires_auth(self, client, mock_central_db):
        resp = client.put(self._url(), json={'business_name': 'X'})
        assert resp.status_code == 401

    def test_no_fields(self, client, admin_headers, mock_central_db):
        resp = client.put(self._url(), json={}, headers=admin_headers)
        assert resp.status_code == 400

    def test_not_found(self, client, admin_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = None
        resp = client.put(self._url(), json={'business_name': 'New Name'},
                          headers=admin_headers)
        assert resp.status_code == 404

    def test_update_success(self, client, admin_headers, mock_central_db):
        updated = FakeRow(
            id=uuid.UUID(TENANT_ID), business_name='Updated',
            email='depot@test.com', status='active',
            updated_at=datetime.utcnow(),
        )
        mock_central_db.execute.return_value.fetchone.return_value = updated

        resp = client.put(self._url(), json={'business_name': 'Updated'},
                          headers=admin_headers)
        assert resp.status_code == 200
        assert resp.get_json()['tenant']['business_name'] == 'Updated'


# =====================================================================
# DELETE TENANT
# =====================================================================

class TestDeleteTenant:
    """DELETE /api/v1/admin/tenant/<id>"""

    def _url(self, tid=TENANT_ID):
        return f'/api/v1/admin/tenant/{tid}'

    def test_requires_auth(self, client, mock_central_db):
        resp = client.delete(self._url())
        assert resp.status_code == 401

    def test_not_found(self, client, admin_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = None
        resp = client.delete(self._url(), headers=admin_headers)
        assert resp.status_code == 404

    @patch('psycopg2.connect')
    def test_delete_success(self, mock_connect, client, admin_headers, mock_central_db, fake_tenant):
        mock_central_db.execute.return_value.fetchone.return_value = fake_tenant
        mock_connect.return_value = MagicMock()

        resp = client.delete(self._url(), headers=admin_headers)
        assert resp.status_code == 200
        assert 'deleted' in resp.get_json()['message'].lower()


# =====================================================================
# LIST USERS
# =====================================================================

class TestListUsers:
    """GET /api/v1/admin/users"""

    URL = '/api/v1/admin/users'

    def test_requires_auth(self, client, mock_central_db):
        assert client.get(self.URL).status_code == 401

    def test_returns_list(self, client, admin_headers, mock_central_db):
        user_row = FakeRow(
            id=uuid.UUID(ADMIN_USER_ID), email='admin@test.com',
            password_hash='xxx', full_name='Admin', phone='123',
            role='admin', tenant_id=None, is_active=True, email_verified=True,
            last_login=datetime.utcnow(), created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            # tenant join fields
            tenant_id_full=None, business_name=None, registration_number=None,
            contact_person=None, tenant_email=None, tenant_phone=None,
            address=None, database_name=None, tenant_status=None,
            tenant_created_at=None,
        )
        mock_central_db.execute.return_value.fetchall.return_value = [user_row]

        resp = client.get(self.URL, headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.get_json()['users']) == 1


# =====================================================================
# UPDATE USER
# =====================================================================

class TestUpdateUser:
    """PUT /api/v1/admin/user/<id>"""

    def _url(self, uid=DEPOT_USER_ID):
        return f'/api/v1/admin/user/{uid}'

    def test_requires_auth(self, client, mock_central_db):
        assert client.put(self._url(), json={'full_name': 'X'}).status_code == 401

    def test_invalid_role(self, client, admin_headers, mock_central_db):
        resp = client.put(self._url(), json={'role': 'superuser'}, headers=admin_headers)
        assert resp.status_code == 400

    def test_no_fields(self, client, admin_headers, mock_central_db):
        resp = client.put(self._url(), json={}, headers=admin_headers)
        assert resp.status_code == 400

    def test_success(self, client, admin_headers, mock_central_db):
        updated_user = FakeRow(
            id=uuid.UUID(DEPOT_USER_ID), email='depot@test.com',
            full_name='Updated', role='depot', is_active=True,
            updated_at=datetime.utcnow(),
        )
        mock_central_db.execute.return_value.fetchone.return_value = updated_user

        resp = client.put(self._url(), json={'full_name': 'Updated'},
                          headers=admin_headers)
        assert resp.status_code == 200


# =====================================================================
# DELETE USER
# =====================================================================

class TestDeleteUser:
    """DELETE /api/v1/admin/user/<id>"""

    def _url(self, uid=DEPOT_USER_ID):
        return f'/api/v1/admin/user/{uid}'

    def test_requires_auth(self, client, mock_central_db):
        assert client.delete(self._url()).status_code == 401

    def test_not_found(self, client, admin_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = None
        assert client.delete(self._url(), headers=admin_headers).status_code == 404

    def test_cannot_delete_self(self, client, admin_headers, mock_central_db):
        self_row = FakeRow(
            id=uuid.UUID(ADMIN_USER_ID), email='admin@test.com',
            role='admin', tenant_id=None,
        )
        mock_central_db.execute.return_value.fetchone.return_value = self_row

        resp = client.delete(f'/api/v1/admin/user/{ADMIN_USER_ID}', headers=admin_headers)
        assert resp.status_code == 400

    @patch('psycopg2.connect')
    def test_delete_depot_user_cascades(self, mock_connect, client, admin_headers,
                                         mock_central_db, fake_tenant):
        """Deleting a depot user also deletes the tenant and database."""
        depot_row = FakeRow(
            id=uuid.UUID(DEPOT_USER_ID), email='depot@test.com',
            role='depot', tenant_id=uuid.UUID(TENANT_ID),
        )
        mock_central_db.execute.return_value.fetchone.side_effect = [
            depot_row,    # user lookup
            fake_tenant,  # tenant lookup
        ]
        mock_connect.return_value = MagicMock()

        resp = client.delete(self._url(), headers=admin_headers)
        assert resp.status_code == 200
        assert 'tenant' in resp.get_json()


# =====================================================================
# SYSTEM HEALTH
# =====================================================================

class TestSystemHealth:
    """GET /api/v1/admin/system-health"""

    URL = '/api/v1/admin/system-health'

    def test_requires_auth(self, client, mock_central_db):
        assert client.get(self.URL).status_code == 401

    @patch('app.blueprints.admin.CentralDB.test_connection', return_value=True)
    def test_healthy(self, _, client, admin_headers, mock_central_db):
        resp = client.get(self.URL, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'healthy'

    @patch('app.blueprints.admin.CentralDB.test_connection', return_value=False)
    def test_degraded(self, _, client, admin_headers, mock_central_db):
        resp = client.get(self.URL, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'degraded'


# =====================================================================
# ADMIN PROFILE
# =====================================================================

class TestAdminProfile:
    """GET / PUT /api/v1/admin/profile"""

    URL = '/api/v1/admin/profile'

    def test_get_requires_auth(self, client, mock_central_db):
        assert client.get(self.URL).status_code == 401

    def test_get_success(self, client, admin_headers, mock_central_db):
        profile = FakeRow(
            id=uuid.UUID(ADMIN_USER_ID), email='admin@test.com',
            full_name='Admin', phone='123', role='admin',
            created_at=datetime.utcnow(), last_login=datetime.utcnow(),
        )
        mock_central_db.execute.return_value.fetchone.return_value = profile
        resp = client.get(self.URL, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.get_json()['user']['email'] == 'admin@test.com'

    def test_update_no_fields(self, client, admin_headers, mock_central_db):
        resp = client.put(self.URL, json={}, headers=admin_headers)
        assert resp.status_code == 400

    def test_update_success(self, client, admin_headers, mock_central_db):
        # email uniqueness check returns None (no conflict)
        updated = FakeRow(
            id=uuid.UUID(ADMIN_USER_ID), email='newemail@test.com',
            full_name='Admin', phone='123', role='admin',
            updated_at=datetime.utcnow(),
        )
        mock_central_db.execute.return_value.fetchone.side_effect = [
            None,     # email is not taken
            updated,  # UPDATE RETURNING
        ]
        resp = client.put(self.URL, json={'email': 'newemail@test.com'},
                          headers=admin_headers)
        assert resp.status_code == 200


# =====================================================================
# CHANGE ADMIN PASSWORD
# =====================================================================

class TestChangePassword:
    """PUT /api/v1/admin/profile/password"""

    URL = '/api/v1/admin/profile/password'

    def test_requires_auth(self, client, mock_central_db):
        assert client.put(self.URL, json={}).status_code == 401

    def test_missing_fields(self, client, admin_headers, mock_central_db):
        resp = client.put(self.URL, json={'current_password': 'x'}, headers=admin_headers)
        assert resp.status_code == 400

    def test_password_mismatch(self, client, admin_headers, mock_central_db):
        resp = client.put(self.URL, json={
            'current_password': 'Old123',
            'new_password': 'New1234',
            'confirm_password': 'Different1',
        }, headers=admin_headers)
        assert resp.status_code == 400

    def test_short_password(self, client, admin_headers, mock_central_db):
        resp = client.put(self.URL, json={
            'current_password': 'Old123',
            'new_password': 'ab',
            'confirm_password': 'ab',
        }, headers=admin_headers)
        assert resp.status_code == 400

    def test_wrong_current_password(self, client, admin_headers, mock_central_db, fake_admin_user):
        mock_central_db.execute.return_value.fetchone.return_value = fake_admin_user
        resp = client.put(self.URL, json={
            'current_password': 'WrongPW1',
            'new_password': 'NewPass1',
            'confirm_password': 'NewPass1',
        }, headers=admin_headers)
        assert resp.status_code == 401

    def test_change_success(self, client, admin_headers, mock_central_db, fake_admin_user):
        mock_central_db.execute.return_value.fetchone.return_value = fake_admin_user
        resp = client.put(self.URL, json={
            'current_password': 'Admin123',
            'new_password': 'NewPass1',
            'confirm_password': 'NewPass1',
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert 'successfully' in resp.get_json()['message'].lower()
