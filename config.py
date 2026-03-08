"""
Configuration settings for the Pharmacy Pricing System
"""

import os
import secrets as _secrets
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load .env file (if exists)
load_dotenv()

# Also load db.env file (if exists)
load_dotenv('db.env')


def _require_env(key, fallback=None):
    """Get env var. In production, fallback is NOT used."""
    val = os.environ.get(key)
    if val:
        return val
    env = os.environ.get('FLASK_ENV', 'development')
    if env == 'production' and fallback is None:
        raise RuntimeError(f"Environment variable '{key}' is required in production")
    return fallback or _secrets.token_hex(32)


def _parse_database_url():
    """Parse DATABASE_URL into individual components if available."""
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        return None
    # Normalize postgres:// to postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    parsed = urlparse(url)
    return {
        'host': parsed.hostname or 'localhost',
        'port': str(parsed.port or 5432),
        'name': (parsed.path or '/pricing_central').lstrip('/'),
        'user': parsed.username or 'postgres',
        'password': parsed.password or 'postgres',
    }


# Pre-parse DATABASE_URL so all config fields are consistent
_db_parts = _parse_database_url()


class Config:
    """Base configuration"""
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    SECRET_KEY = _require_env('SECRET_KEY')
    JWT_SECRET_KEY = _require_env('JWT_SECRET_KEY', fallback=SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRES = 604800  # 7 days
    
    # Central Database — parsed from DATABASE_URL when available
    CENTRAL_DB_HOST = os.environ.get('CENTRAL_DB_HOST') or (_db_parts['host'] if _db_parts else 'localhost')
    CENTRAL_DB_PORT = os.environ.get('CENTRAL_DB_PORT') or (_db_parts['port'] if _db_parts else '5432')
    CENTRAL_DB_NAME = os.environ.get('CENTRAL_DB_NAME') or (_db_parts['name'] if _db_parts else 'pricing_central')
    CENTRAL_DB_USER = os.environ.get('CENTRAL_DB_USER') or (_db_parts['user'] if _db_parts else 'postgres')
    CENTRAL_DB_PASSWORD = os.environ.get('CENTRAL_DB_PASSWORD') or (_db_parts['password'] if _db_parts else 'postgres')
    
    # PostgreSQL Admin (for creating tenant databases)
    PG_ADMIN_USER = os.environ.get('PG_ADMIN_USER') or CENTRAL_DB_USER
    PG_ADMIN_PASSWORD = os.environ.get('PG_ADMIN_PASSWORD') or CENTRAL_DB_PASSWORD
    PG_ADMIN_HOST = os.environ.get('PG_ADMIN_HOST') or CENTRAL_DB_HOST
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
    
    # Bcrypt settings
    BCRYPT_LOG_ROUNDS = 12
    
    # Rate limiting
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'True').lower() == 'true'
    RATELIMIT_PER_MINUTE = 100
    
    # Tenant database naming
    TENANT_DB_PREFIX = 'tenant_'
    
    # Allowed CORS origins (comma-separated in env, or '*' for dev)
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    
    @staticmethod
    def get_central_db_uri():
        """Get central database connection URI"""
        # Support Render's DATABASE_URL (or any single connection string)
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Render uses 'postgres://' but SQLAlchemy 2.x requires 'postgresql://'
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            return database_url
        return f"postgresql://{Config.CENTRAL_DB_USER}:{Config.CENTRAL_DB_PASSWORD}@{Config.CENTRAL_DB_HOST}:{Config.CENTRAL_DB_PORT}/{Config.CENTRAL_DB_NAME}"
    
    @staticmethod
    def get_tenant_db_uri(tenant_db_name):
        """Get tenant database connection URI"""
        # Use the same host/credentials derived from DATABASE_URL or individual env vars
        return f"postgresql://{Config.CENTRAL_DB_USER}:{Config.CENTRAL_DB_PASSWORD}@{Config.CENTRAL_DB_HOST}:{Config.CENTRAL_DB_PORT}/{tenant_db_name}"
