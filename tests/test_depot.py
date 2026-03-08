"""
Tests for the Depot Blueprint (/api/v1/depot)
Covers: upload, price-lists, medicines, statistics, upload-history,
        medicine CRUD, price-list deletion, OCR upload confirm
"""

import io
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from decimal import Decimal

import pytest

from tests.conftest import (
    FakeRow, ADMIN_USER_ID, DEPOT_USER_ID, TENANT_ID, TENANT_DB_NAME,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tenant_row():
    return FakeRow(database_name=TENANT_DB_NAME)


def _csv_bytes(header='medicine_name,unit_price,expiry_date',
               rows=None):
    """Generate a minimal CSV file as bytes."""
    if rows is None:
        rows = ['Paracetamol,2.50,2027-01-01', 'Ibuprofen,5.00,2027-06-15']
    content = header + '\n' + '\n'.join(rows)
    return content.encode('utf-8')


# =====================================================================
# FILE UPLOAD
# =====================================================================

class TestUpload:
    """POST /api/v1/depot/upload"""

    URL = '/api/v1/depot/upload'

    def test_requires_auth(self, client, mock_central_db):
        assert client.post(self.URL).status_code == 401

    def test_requires_depot_role(self, client, admin_headers, mock_central_db):
        assert client.post(self.URL, headers=admin_headers).status_code == 403

    def test_no_file(self, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        data = {}  # no file key
        resp = client.post(self.URL, data=data, content_type='multipart/form-data',
                           headers={'Authorization': depot_headers['Authorization']})
        assert resp.status_code == 400

    def test_invalid_extension(self, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        data = {'file': (io.BytesIO(b'data'), 'prices.txt')}
        resp = client.post(self.URL, data=data, content_type='multipart/form-data',
                           headers={'Authorization': depot_headers['Authorization']})
        assert resp.status_code == 400

    @patch('app.blueprints.depot.TenantDBManager')
    def test_upload_csv_success(self, MockTDBM, client, depot_headers, mock_central_db):
        """Upload a valid CSV file => 201."""
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()

        tenant_sess = MagicMock()
        # check_result for existing medicine -> None (insert new)
        tenant_sess.execute.return_value.fetchone.return_value = None
        tenant_sess.execute.return_value.rowcount = 0
        tenant_sess.execute.return_value.scalar.return_value = 0
        MockTDBM.get_session.return_value = tenant_sess

        csv_data = _csv_bytes()
        data = {'file': (io.BytesIO(csv_data), 'prices.csv')}

        resp = client.post(self.URL, data=data, content_type='multipart/form-data',
                           headers={'Authorization': depot_headers['Authorization']})
        assert resp.status_code == 201
        body = resp.get_json()
        assert 'statistics' in body
        assert body['statistics']['valid_items'] > 0


# =====================================================================
# GET PRICE LISTS
# =====================================================================

class TestGetPriceLists:
    """GET /api/v1/depot/price-lists"""

    URL = '/api/v1/depot/price-lists'

    def test_requires_auth(self, client, mock_central_db):
        assert client.get(self.URL).status_code == 401

    def test_requires_depot(self, client, admin_headers, mock_central_db):
        assert client.get(self.URL, headers=admin_headers).status_code == 403

    @patch('app.blueprints.depot.TenantDBManager')
    def test_returns_list(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()

        pl_row = FakeRow(
            id=uuid.uuid4(), version=1, status='active',
            file_name='test.csv', total_items=10, valid_items=10,
            invalid_items=0, activated_at=datetime.utcnow(), created_at=datetime.utcnow(),
        )
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchall.return_value = [pl_row]
        tenant_sess.execute.return_value.scalar.return_value = 1
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.get(self.URL, headers=depot_headers)
        assert resp.status_code == 200
        assert 'price_lists' in resp.get_json()


# =====================================================================
# GET MEDICINES
# =====================================================================

class TestGetMedicines:
    """GET /api/v1/depot/medicines"""

    URL = '/api/v1/depot/medicines'

    def test_requires_auth(self, client, mock_central_db):
        assert client.get(self.URL).status_code == 401

    @patch('app.blueprints.depot.TenantDBManager')
    def test_returns_medicines(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()

        med = FakeRow(
            id=uuid.uuid4(), medicine_name='Paracetamol',
            unit_price=Decimal('2.50'), expiry_date=datetime(2027, 1, 1).date(),
            is_active=True, file_name='test.csv',
            price_list_status='active', activated_at=datetime.utcnow(),
        )
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchall.return_value = [med]
        tenant_sess.execute.return_value.scalar.return_value = 1
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.get(self.URL, headers=depot_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['medicines']) == 1
        assert data['medicines'][0]['medicine_name'] == 'Paracetamol'

    @patch('app.blueprints.depot.TenantDBManager')
    def test_search_filter(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchall.return_value = []
        tenant_sess.execute.return_value.scalar.return_value = 0
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.get(f'{self.URL}?search=aspirin', headers=depot_headers)
        assert resp.status_code == 200


# =====================================================================
# STATISTICS
# =====================================================================

class TestStatistics:
    """GET /api/v1/depot/statistics"""

    URL = '/api/v1/depot/statistics'

    def test_requires_auth(self, client, mock_central_db):
        assert client.get(self.URL).status_code == 401

    @patch('app.blueprints.depot.TenantDBManager')
    def test_returns_stats(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        stats = FakeRow(total_medicines=50, total_uploads=3, active_price_lists=1)
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchone.return_value = stats
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.get(self.URL, headers=depot_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_medicines'] == 50
        assert data['total_uploads'] == 3


# =====================================================================
# UPLOAD HISTORY
# =====================================================================

class TestUploadHistory:
    """GET /api/v1/depot/upload-history"""

    URL = '/api/v1/depot/upload-history'

    def test_requires_auth(self, client, mock_central_db):
        assert client.get(self.URL).status_code == 401

    @patch('app.blueprints.depot.TenantDBManager')
    def test_returns_history(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        hist = FakeRow(
            id=uuid.uuid4(), file_name='test.csv', file_size_bytes=1024,
            upload_timestamp=datetime.utcnow(), records_processed=10,
            records_success=9, records_failed=1, status='completed',
        )
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchall.return_value = [hist]
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.get(self.URL, headers=depot_headers)
        assert resp.status_code == 200
        assert len(resp.get_json()['history']) == 1


# =====================================================================
# DELETE UPLOAD HISTORY
# =====================================================================

class TestDeleteUploadHistory:
    """DELETE /api/v1/depot/upload-history/<id>"""

    def _url(self, hid=None):
        return f'/api/v1/depot/upload-history/{hid or uuid.uuid4()}'

    def test_requires_auth(self, client, mock_central_db):
        assert client.delete(self._url()).status_code == 401

    @patch('app.blueprints.depot.TenantDBManager')
    def test_not_found(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchone.return_value = None
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.delete(self._url(), headers=depot_headers)
        assert resp.status_code == 404

    @patch('app.blueprints.depot.TenantDBManager')
    def test_delete_success(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        hist = FakeRow(id=uuid.uuid4(), file_name='test.csv')
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchone.return_value = hist
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.delete(self._url(hist.id), headers=depot_headers)
        assert resp.status_code == 200


# =====================================================================
# UPDATE MEDICINE
# =====================================================================

class TestUpdateMedicine:
    """PUT /api/v1/depot/medicine/<id>"""

    def _url(self, mid=None):
        return f'/api/v1/depot/medicine/{mid or uuid.uuid4()}'

    def test_requires_auth(self, client, mock_central_db):
        assert client.put(self._url(), json={}).status_code == 401

    @patch('app.blueprints.depot.TenantDBManager')
    def test_no_fields(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        tenant_sess = MagicMock()
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.put(self._url(), json={}, headers=depot_headers)
        assert resp.status_code == 400

    @patch('app.blueprints.depot.TenantDBManager')
    def test_update_success(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        updated = FakeRow(id=uuid.uuid4(), medicine_name='Paracetamol', unit_price=Decimal('3.00'))
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchone.return_value = updated
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.put(self._url(updated.id),
                          json={'unit_price': 3.00},
                          headers=depot_headers)
        assert resp.status_code == 200


# =====================================================================
# DELETE MEDICINE
# =====================================================================

class TestDeleteMedicine:
    """DELETE /api/v1/depot/medicine/<id>"""

    def _url(self, mid=None):
        return f'/api/v1/depot/medicine/{mid or uuid.uuid4()}'

    def test_requires_auth(self, client, mock_central_db):
        assert client.delete(self._url()).status_code == 401

    @patch('app.blueprints.depot.TenantDBManager')
    def test_not_found(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchone.return_value = None
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.delete(self._url(), headers=depot_headers)
        assert resp.status_code == 404

    @patch('app.blueprints.depot.TenantDBManager')
    def test_delete_success(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        med = FakeRow(id=uuid.uuid4(), medicine_name='Aspirin')
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchone.return_value = med
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.delete(self._url(med.id), headers=depot_headers)
        assert resp.status_code == 200


# =====================================================================
# UPLOAD OCR CONFIRM
# =====================================================================

class TestOCRConfirm:
    """POST /api/v1/depot/upload-ocr-confirm"""

    URL = '/api/v1/depot/upload-ocr-confirm'

    def test_requires_auth(self, client, mock_central_db):
        assert client.post(self.URL, json={}).status_code == 401

    def test_no_records(self, client, depot_headers, mock_central_db):
        resp = client.post(self.URL, json={'records': []}, headers=depot_headers)
        assert resp.status_code == 400

    @patch('app.blueprints.depot.TenantDBManager')
    def test_confirm_success(self, MockTDBM, client, depot_headers, mock_central_db):
        mock_central_db.execute.return_value.fetchone.return_value = _tenant_row()
        tenant_sess = MagicMock()
        tenant_sess.execute.return_value.fetchone.return_value = None  # no existing med
        tenant_sess.execute.return_value.rowcount = 0
        MockTDBM.get_session.return_value = tenant_sess

        resp = client.post(self.URL, json={
            'records': [
                {'medicine_name': 'Paracetamol', 'unit_price': 2.50, 'expiry_date': '2027-01-01'},
                {'medicine_name': 'Aspirin', 'unit_price': 3.00, 'expiry_date': '2027-06-15'},
            ]
        }, headers=depot_headers)
        assert resp.status_code == 201


# =====================================================================
# NO-TENANT-ID EDGE CASE
# =====================================================================

class TestNoTenantId:
    """Depot endpoints return 400 when user has no tenant_id."""

    ENDPOINTS_GET = [
        '/api/v1/depot/price-lists',
        '/api/v1/depot/medicines',
        '/api/v1/depot/statistics',
        '/api/v1/depot/upload-history',
    ]

    def _no_tenant_headers(self, app):
        """Build JWT headers for a depot user without tenant_id."""
        import jwt as pyjwt
        payload = {
            'user_id': DEPOT_USER_ID,
            'email': 'depot@test.com',
            'role': 'depot',
            'tenant_id': None,
            'exp': datetime.utcnow() + timedelta(hours=1),
            'iat': datetime.utcnow(),
        }
        token = pyjwt.encode(payload, 'test-jwt-secret-key-for-tests', algorithm='HS256')
        return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    @pytest.mark.parametrize('url', ENDPOINTS_GET)
    def test_get_no_tenant(self, url, client, app, mock_central_db):
        resp = client.get(url, headers=self._no_tenant_headers(app))
        assert resp.status_code == 400
