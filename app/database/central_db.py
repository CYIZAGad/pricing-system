"""
Central Database Connection Manager
Connects to the pre-existing central database (imported)
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from config import Config
import logging

logger = logging.getLogger(__name__)


class CentralDB:
    """Manages connection to central database"""
    
    _engine = None
    _session_factory = None
    
    @classmethod
    def initialize(cls):
        """Initialize central database connection"""
        if cls._engine is None:
            try:
                uri = Config.get_central_db_uri()
                cls._engine = create_engine(
                    uri,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10,
                    pool_recycle=300,
                    pool_timeout=10,
                    connect_args={'connect_timeout': 10},
                    echo=False
                )
                cls._session_factory = scoped_session(
                    sessionmaker(bind=cls._engine, autocommit=False, autoflush=False)
                )
                logger.info("Central database connection initialized")
            except Exception as e:
                logger.error(f"Failed to initialize central database: {e}")
                raise
    
    @classmethod
    def get_session(cls):
        """Get a database session"""
        if cls._session_factory is None:
            cls.initialize()
        return cls._session_factory()
    
    @classmethod
    def close_session(cls):
        """Close current session"""
        if cls._session_factory:
            cls._session_factory.remove()
    
    @classmethod
    def test_connection(cls):
        """Test database connection"""
        try:
            session = cls.get_session()
            result = session.execute(text("SELECT 1"))
            session.close()
            return True
        except Exception as e:
            logger.error(f"Central DB connection test failed: {e}")
            return False
