"""
Tenant Database Creator Service
Automatically creates tenant databases with all required tables
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
from config import Config
import logging
import re

logger = logging.getLogger(__name__)


class TenantDatabaseCreator:
    """Creates tenant databases and required schema"""
    
    def __init__(self):
        self.admin_conn_params = {
            'host': Config.PG_ADMIN_HOST,
            'port': Config.CENTRAL_DB_PORT,
            'user': Config.PG_ADMIN_USER,
            'password': Config.PG_ADMIN_PASSWORD,
            'dbname': Config.CENTRAL_DB_NAME
        }
    
    def sanitize_db_name(self, name):
        """Sanitize database name to be PostgreSQL-safe"""
        # Remove special characters, keep alphanumeric and underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Ensure it starts with a letter or underscore
        if not re.match(r'^[a-zA-Z_]', sanitized):
            sanitized = 'db_' + sanitized
        # Limit length
        sanitized = sanitized[:63]  # PostgreSQL limit
        return sanitized.lower()
    
    def create_tenant_database(self, tenant_db_name):
        """
        Create tenant database and all required tables
        Returns: (success: bool, database_name: str, error: str)
        """
        # Sanitize database name
        safe_db_name = self.sanitize_db_name(tenant_db_name)
        full_db_name = f"{Config.TENANT_DB_PREFIX}{safe_db_name}"
        
        return self.create_tenant_database_with_name(full_db_name)
    
    def create_tenant_database_with_name(self, full_db_name):
        """
        Create tenant database with a specific name and all required tables
        Returns: (success: bool, database_name: str, error: str)
        """
        admin_conn = None
        tenant_engine = None
        
        try:
            # Step 1: Connect as admin to create database
            admin_conn = psycopg2.connect(**self.admin_conn_params)
            admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            admin_cursor = admin_conn.cursor()
            
            # Check if database already exists
            admin_cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (full_db_name,)
            )
            if admin_cursor.fetchone():
                logger.warning(f"Database {full_db_name} already exists")
                admin_cursor.close()
                admin_conn.close()
                return True, full_db_name, None
            
            # Create database
            admin_cursor.execute(f'CREATE DATABASE "{full_db_name}"')
            admin_cursor.close()
            admin_conn.close()
            logger.info(f"Created database: {full_db_name}")
            
            # Step 2: Connect to new database and create tables
            tenant_uri = Config.get_tenant_db_uri(full_db_name)
            tenant_engine = create_engine(tenant_uri)
            
            with tenant_engine.connect() as conn:
                # Create all required tables
                self._create_price_lists_table(conn)
                self._create_medicines_table(conn)
                self._create_upload_history_table(conn)
                
                conn.commit()
            
            logger.info(f"Successfully created tenant database: {full_db_name}")
            return True, full_db_name, None
            
        except Exception as e:
            error_msg = f"Failed to create tenant database: {str(e)}"
            logger.error(error_msg)
            
            # Rollback: Try to drop database if creation failed
            if admin_conn:
                try:
                    admin_conn = psycopg2.connect(**self.admin_conn_params)
                    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                    admin_cursor = admin_conn.cursor()
                    admin_cursor.execute(f'DROP DATABASE IF EXISTS "{full_db_name}"')
                    admin_cursor.close()
                    admin_conn.close()
                except:
                    pass
            
            return False, None, error_msg
    
    def _create_price_lists_table(self, conn):
        """Create price_lists table"""
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS price_lists (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                status VARCHAR(20) NOT NULL DEFAULT 'active' 
                    CHECK (status IN ('active', 'archived', 'processing', 'failed')),
                file_name VARCHAR(255),
                file_url TEXT,
                total_items INTEGER DEFAULT 0,
                valid_items INTEGER DEFAULT 0,
                invalid_items INTEGER DEFAULT 0,
                processing_errors JSONB,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                archived_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_price_lists_tenant 
            ON price_lists(tenant_id)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_price_lists_status 
            ON price_lists(status)
        """))
    
    def _create_medicines_table(self, conn):
        """Create medicines table with name, price, and expiry_date"""
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS medicines (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                price_list_id UUID NOT NULL,
                medicine_name VARCHAR(200) NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL CHECK (unit_price > 0),
                expiry_date DATE NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_medicine_per_list 
                    UNIQUE(price_list_id, medicine_name)
            )
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_medicines_name 
            ON medicines(medicine_name)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_medicines_price 
            ON medicines(unit_price)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_medicines_active 
            ON medicines(is_active)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_medicines_expiry_date 
            ON medicines(expiry_date)
        """))
        
        # Full-text search index
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_medicines_search 
            ON medicines USING gin(to_tsvector('english', medicine_name))
        """))
    
    def _create_upload_history_table(self, conn):
        """Create upload_history table"""
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS upload_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL,
                file_name VARCHAR(255),
                file_size_bytes BIGINT,
                upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                records_processed INTEGER DEFAULT 0,
                records_success INTEGER DEFAULT 0,
                records_failed INTEGER DEFAULT 0,
                status VARCHAR(20) CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
                error_log JSONB,
                processing_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_upload_history_user 
            ON upload_history(user_id)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_upload_history_timestamp 
            ON upload_history(upload_timestamp)
        """))
    
    # Download logs table removed - no longer needed without pharmacy users
