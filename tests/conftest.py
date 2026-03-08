"""
Shared pytest fixtures and test configuration.

All database interactions are mocked so the test suite can run
without a real PostgreSQL instance.
"""

import os
import sys
import uuid
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Test Config
# ---------------------------------------------------------------------------

class TestConfig:
    """Configuration used only during testing."""
    FLASK_ENV = 'testing'
    SECRET_KEY = 'test-secret-key-for-unit-tests'
    JWT_SECRET_KEY = 'test-jwt-secret-key-for-tests'
    JWT_ACCESS_TOKEN_EXPIRES = 3600
    JWT_REFRESH_TOKEN_EXPIRES = 86400
    CENTRAL_DB_HOST = 'localhost'
    CENTRAL_DB_PORT = '5432'
    CENTRAL_DB_NAME = 'test_pricing_central'
    CENTRAL_DB_USER = 'postgres'
    CENTRAL_DB_PASSWORD = 'postgres'
    PG_ADMIN_USER = 'postgres'
    PG_ADMIN_PASSWORD = 'postgres'
    PG_ADMIN_HOST = 'localhost'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
    BCRYPT_LOG_ROUNDS = 4  # Faster hashing for tests
    RATELIMIT_ENABLED = False
    RATELIMIT_PER_MINUTE = 1000
    TENANT_DB_PREFIX = 'tenant_'
    CORS_ORIGINS = '*'
    TESTING = True

    @staticmethod
    def get_central_db_uri():
        return 'sqlite://'  # Not actually used; we mock DB access

    @staticmethod
    def get_tenant_db_uri(tenant_db_name):
        return 'sqlite://'


# ---------------------------------------------------------------------------
# Helper: fake row object (mimics SQLAlchemy Row with attribute access)
# ---------------------------------------------------------------------------

class FakeRow:
    """Mimics a SQLAlchemy result row with attribute access."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Static IDs used throughout the test suite
# ---------------------------------------------------------------------------

ADMIN_USER_ID = str(uuid.uuid4())
DEPOT_USER_ID = str(uuid.uuid4())
TENANT_ID = str(uuid.uuid4())
TENANT_DB_NAME = 'tenant_test_depot'


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def app():
    """Create a Flask app using TestConfig (once per session)."""
    from app import create_app
    application = create_app(TestConfig)
    application.config['TESTING'] = True
    return application


@pytest.fixture()
def client(app):
    """Flask test client per test."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Fake database session
# ---------------------------------------------------------------------------

def _make_fake_session():
    """Create a MagicMock that behaves like a SQLAlchemy session."""
    session = MagicMock()
    session.execute.return_value = MagicMock(fetchone=MagicMock(return_value=None),
                                              fetchall=MagicMock(return_value=[]),
                                              scalar=MagicMock(return_value=0))
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture()
def mock_central_db():
    """Patch CentralDB.get_session to return a MagicMock session."""
    with patch('app.database.central_db.CentralDB.get_session') as mock_get:
        fake = _make_fake_session()
        mock_get.return_value = fake
        yield fake


@pytest.fixture()
def mock_tenant_db():
    """Patch TenantDBManager.get_session to return a MagicMock session."""
    with patch('app.database.tenant_db.TenantDBManager.get_session') as mock_get:
        fake = _make_fake_session()
        mock_get.return_value = fake
        yield fake


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_token(app):
    """Generate a valid JWT token for an admin user."""
    import jwt as pyjwt
    payload = {
        'user_id': ADMIN_USER_ID,
        'email': 'admin@test.com',
        'role': 'admin',
        'tenant_id': None,
        'exp': datetime.utcnow() + timedelta(hours=1),
        'iat': datetime.utcnow(),
    }
    return pyjwt.encode(payload, TestConfig.JWT_SECRET_KEY, algorithm='HS256')


@pytest.fixture()
def depot_token(app):
    """Generate a valid JWT token for a depot user."""
    import jwt as pyjwt
    payload = {
        'user_id': DEPOT_USER_ID,
        'email': 'depot@test.com',
        'role': 'depot',
        'tenant_id': TENANT_ID,
        'exp': datetime.utcnow() + timedelta(hours=1),
        'iat': datetime.utcnow(),
    }
    return pyjwt.encode(payload, TestConfig.JWT_SECRET_KEY, algorithm='HS256')


@pytest.fixture()
def admin_headers(admin_token):
    """Authorization header for admin requests."""
    return {
        'Authorization': f'Bearer {admin_token}',
        'Content-Type': 'application/json',
    }


@pytest.fixture()
def depot_headers(depot_token):
    """Authorization header for depot requests."""
    return {
        'Authorization': f'Bearer {depot_token}',
        'Content-Type': 'application/json',
    }


# ---------------------------------------------------------------------------
# Reusable fake user / tenant rows
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_admin_user():
    """Return a FakeRow representing an admin user."""
    from app.utils.auth import hash_password
    return FakeRow(
        id=uuid.UUID(ADMIN_USER_ID),
        email='admin@test.com',
        password_hash=hash_password('Admin123'),
        full_name='Test Admin',
        role='admin',
        tenant_id=None,
        is_active=True,
        email_verified=True,
        phone='1234567890',
        last_login=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture()
def fake_depot_user():
    """Return a FakeRow representing a depot user."""
    from app.utils.auth import hash_password
    return FakeRow(
        id=uuid.UUID(DEPOT_USER_ID),
        email='depot@test.com',
        password_hash=hash_password('Depot123'),
        full_name='Test Depot',
        role='depot',
        tenant_id=uuid.UUID(TENANT_ID),
        is_active=True,
        email_verified=True,
        phone='9876543210',
        last_login=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture()
def fake_tenant():
    """Return a FakeRow representing a tenant."""
    return FakeRow(
        id=uuid.UUID(TENANT_ID),
        business_name='Test Depot Ltd',
        registration_number='REG-001',
        contact_person='John Doe',
        email='depot@test.com',
        phone='9876543210',
        address='123 Test Street',
        database_name=TENANT_DB_NAME,
        status='active',
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture()
def fake_session_row():
    """Return a FakeRow that mimics a valid user_sessions row."""
    return FakeRow(
        user_id=uuid.UUID(ADMIN_USER_ID),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
