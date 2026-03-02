"""
Tenant Database Manager
Handles dynamic connections to tenant-specific databases
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from config import Config
import logging
from threading import local

logger = logging.getLogger(__name__)

# Thread-local storage for tenant sessions
_thread_local = local()


class TenantDBManager:
    """Manages tenant database connections"""
    
    _engines = {}  # Cache of engine connections per tenant
    
    @classmethod
    def get_engine(cls, tenant_db_name):
        """Get or create engine for tenant database"""
        if tenant_db_name not in cls._engines:
            try:
                uri = Config.get_tenant_db_uri(tenant_db_name)
                cls._engines[tenant_db_name] = create_engine(
                    uri,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10,
                    echo=False
                )
                logger.info(f"Created engine for tenant database: {tenant_db_name}")
            except Exception as e:
                logger.error(f"Failed to create engine for {tenant_db_name}: {e}")
                raise
        return cls._engines[tenant_db_name]
    
    @classmethod
    def get_session(cls, tenant_db_name):
        """Get a session for tenant database"""
        engine = cls.get_engine(tenant_db_name)
        session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        return session_factory()
    
    @classmethod
    def test_connection(cls, tenant_db_name):
        """Test connection to tenant database"""
        try:
            session = cls.get_session(tenant_db_name)
            result = session.execute(text("SELECT 1"))
            session.close()
            return True
        except Exception as e:
            logger.error(f"Tenant DB connection test failed for {tenant_db_name}: {e}")
            return False
    
    @classmethod
    def create_tenant_database(cls, tenant_db_name):
        """
        Create a new tenant database and all required tables
        This is called when a new depot tenant is created
        """
        from app.services.tenant_creator import TenantDatabaseCreator
        creator = TenantDatabaseCreator()
        return creator.create_tenant_database(tenant_db_name)
