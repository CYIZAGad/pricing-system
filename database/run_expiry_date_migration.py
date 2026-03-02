"""
Migration Runner: Add expiry_date column to all tenant databases
This script automatically runs the expiry_date migration on all existing tenant databases
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_all_tenant_databases():
    """Get list of all tenant database names from central database"""
    try:
        central_uri = Config.get_central_db_uri()
        engine = create_engine(central_uri)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT database_name 
                FROM tenants 
                WHERE status = 'active'
                ORDER BY database_name
            """))
            databases = [row[0] for row in result.fetchall()]
        
        engine.dispose()
        return databases
    except Exception as e:
        logger.error(f"Failed to get tenant databases: {e}")
        raise


def run_migration_on_database(db_name):
    """Run expiry_date migration on a specific tenant database"""
    try:
        logger.info(f"Migrating database: {db_name}")
        
        tenant_uri = Config.get_tenant_db_uri(db_name)
        engine = create_engine(tenant_uri)
        
        with engine.connect() as conn:
            # Check if column already exists
            check_result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'medicines' 
                AND column_name = 'expiry_date'
            """))
            
            if check_result.fetchone():
                logger.info(f"  ✓ Column expiry_date already exists in {db_name}, skipping...")
                conn.commit()
                engine.dispose()
                return True, "Already migrated"
            
            # Step 1: Add the expiry_date column (nullable first)
            logger.info(f"  → Adding expiry_date column...")
            conn.execute(text("""
                ALTER TABLE medicines 
                ADD COLUMN IF NOT EXISTS expiry_date DATE
            """))
            conn.commit()
            
            # Step 2: Create index on expiry_date
            logger.info(f"  → Creating index on expiry_date...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_medicines_expiry_date 
                ON medicines(expiry_date)
            """))
            conn.commit()
            
            # Step 3: Set default expiry date for existing records (1 year from now)
            logger.info(f"  → Setting default expiry dates for existing records...")
            result = conn.execute(text("""
                UPDATE medicines 
                SET expiry_date = CURRENT_DATE + INTERVAL '1 year'
                WHERE expiry_date IS NULL
            """))
            rows_updated = result.rowcount
            conn.commit()
            logger.info(f"  → Updated {rows_updated} existing records with default expiry date")
            
            # Step 4: Make the column NOT NULL (required field)
            logger.info(f"  → Making expiry_date NOT NULL...")
            conn.execute(text("""
                ALTER TABLE medicines 
                ALTER COLUMN expiry_date SET NOT NULL
            """))
            conn.commit()
            
            logger.info(f"  ✓ Successfully migrated {db_name}")
            engine.dispose()
            return True, f"Migrated successfully ({rows_updated} records updated)"
            
    except Exception as e:
        logger.error(f"  ✗ Failed to migrate {db_name}: {e}")
        return False, str(e)


def main():
    """Main migration runner"""
    logger.info("=" * 60)
    logger.info("Expiry Date Migration Runner")
    logger.info("=" * 60)
    logger.info("")
    
    try:
        # Get all tenant databases
        logger.info("Fetching list of tenant databases...")
        databases = get_all_tenant_databases()
        
        if not databases:
            logger.warning("No tenant databases found!")
            return
        
        logger.info(f"Found {len(databases)} tenant database(s)")
        logger.info("")
        
        # Run migration on each database
        results = []
        for db_name in databases:
            success, message = run_migration_on_database(db_name)
            results.append({
                'database': db_name,
                'success': success,
                'message': message
            })
            logger.info("")
        
        # Summary
        logger.info("=" * 60)
        logger.info("Migration Summary")
        logger.info("=" * 60)
        
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        
        logger.info(f"Total databases: {len(results)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info("")
        
        if failed > 0:
            logger.warning("Failed migrations:")
            for r in results:
                if not r['success']:
                    logger.warning(f"  - {r['database']}: {r['message']}")
        
        logger.info("=" * 60)
        logger.info("Migration completed!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
