"""
Admin Blueprint
Handles tenant management and system administration
"""

from flask import Blueprint, request, jsonify
from app.database.central_db import CentralDB
from app.database.tenant_db import TenantDBManager
from app.services.tenant_creator import TenantDatabaseCreator
from app.utils.auth import require_auth, require_role, hash_password
from sqlalchemy import text
from config import Config
import uuid
import re
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)


def _safe_db_identifier(name):
    """Sanitize a database name to prevent SQL injection in DDL statements.
    Only allows alphanumeric characters and underscores."""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"Invalid database identifier: {name}")
    return name


@admin_bp.route('/tenant', methods=['POST'])
@require_auth
@require_role('admin')
def create_tenant():
    """Create a new tenant (depot) and automatically create its database"""
    try:
        data = request.get_json()
        business_name = data.get('business_name')
        registration_number = data.get('registration_number')
        contact_person = data.get('contact_person')
        email = data.get('email')
        phone = data.get('phone')
        address = data.get('address')
        password = data.get('password')
        password_confirm = data.get('password_confirm')
        
        if not business_name or not email:
            return jsonify({'error': 'Business name and email are required'}), 400
        
        # Validate password
        if not password or len(password) < 6:
            return jsonify({'error': 'Password is required and must be at least 6 characters'}), 400
        
        if password != password_confirm:
            return jsonify({'error': 'Passwords do not match'}), 400
        
        session = CentralDB.get_session()
        
        # Check if depot already exists by email
        existing_email = session.execute(
            text("SELECT id, business_name FROM tenants WHERE email = :email"),
            {'email': email}
        ).fetchone()
        
        if existing_email:
            session.close()
            return jsonify({
                'error': 'Depot already exists',
                'message': f'A depot with email "{email}" already exists (Business: {existing_email.business_name})'
            }), 409
        
        # Check if depot already exists by registration number (if provided)
        if registration_number:
            existing_reg = session.execute(
                text("SELECT id, business_name FROM tenants WHERE registration_number = :reg"),
                {'reg': registration_number}
            ).fetchone()
            
            if existing_reg:
                session.close()
                return jsonify({
                    'error': 'Depot already exists',
                    'message': f'A depot with registration number "{registration_number}" already exists (Business: {existing_reg.business_name})'
                }), 409
        
        # Generate tenant ID
        tenant_id = uuid.uuid4()
        
        # Create tenant database first
        creator = TenantDatabaseCreator()
        
        # Generate a unique database name by checking existing ones
        base_db_name = creator.sanitize_db_name(business_name)
        full_db_name = f"{Config.TENANT_DB_PREFIX}{base_db_name}"
        
        # Check if database name already exists in tenants table
        counter = 0
        while True:
            existing_db = session.execute(
                text("SELECT id FROM tenants WHERE database_name = :db_name"),
                {'db_name': full_db_name}
            ).fetchone()
            
            if not existing_db:
                # Database name is available, use it
                break
            
            # Name exists, try with a suffix
            counter += 1
            full_db_name = f"{Config.TENANT_DB_PREFIX}{base_db_name}_{counter}"
            if counter > 100:  # Safety limit
                session.close()
                return jsonify({
                    'error': 'Failed to generate unique database name',
                    'message': 'Could not find an available database name. Please try a different business name.'
                }), 500
        
        # Now create the database with the unique name
        success, database_name, error = creator.create_tenant_database_with_name(full_db_name)
        
        if not success:
            session.close()
            logger.error(f"Failed to create tenant database: {error}")
            return jsonify({
                'error': 'Failed to create depot database',
                'message': error or 'Database creation failed. Please check PostgreSQL connection and permissions.'
            }), 500
        
        try:
            # Insert tenant into central database
            result = session.execute(
                text("""
                    INSERT INTO tenants (id, business_name, registration_number, contact_person, 
                        email, phone, address, database_name, status)
                    VALUES (:id, :business_name, :registration_number, :contact_person,
                        :email, :phone, :address, :database_name, 'active')
                    RETURNING id, business_name, email, database_name, status, created_at
                """),
                {
                    'id': tenant_id,
                    'business_name': business_name,
                    'registration_number': registration_number,
                    'contact_person': contact_person,
                    'email': email,
                    'phone': phone,
                    'address': address,
                    'database_name': database_name
                }
            )
            tenant = result.fetchone()
        except Exception as insert_error:
            # Handle unique constraint violation for database_name (race condition)
            error_str = str(insert_error)
            if 'database_name_key' in error_str or 'UniqueViolation' in error_str:
                session.rollback()
                session.close()
                
                # Try to clean up the database we just created
                try:
                    import psycopg2
                    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
                    admin_conn = psycopg2.connect(
                        host=Config.PG_ADMIN_HOST,
                        port=Config.CENTRAL_DB_PORT,
                        user=Config.PG_ADMIN_USER,
                        password=Config.PG_ADMIN_PASSWORD,
                        database='postgres'
                    )
                    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                    admin_cursor = admin_conn.cursor()
                    safe_name = _safe_db_identifier(database_name)
                    admin_cursor.execute(f'DROP DATABASE IF EXISTS "{safe_name}"')
                    admin_cursor.close()
                    admin_conn.close()
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup database {database_name}: {cleanup_error}")
                
                return jsonify({
                    'error': 'Database name conflict',
                    'message': f'A depot with database name "{database_name}" already exists. Please try again with a different business name, or contact support to clean up the existing record.'
                }), 409
            else:
                # Re-raise if it's a different error
                raise
        
        # Create depot manager user account (outside try/except block)
        try:
            # Check if user with this email already exists
            existing_user = session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {'email': email}
            ).fetchone()
            
            if existing_user:
                # Rollback tenant creation if user exists
                session.rollback()
                session.close()
                # Try to clean up the database we just created
                try:
                    import psycopg2
                    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
                    admin_conn = psycopg2.connect(
                        host=Config.PG_ADMIN_HOST,
                        port=Config.CENTRAL_DB_PORT,
                        user=Config.PG_ADMIN_USER,
                        password=Config.PG_ADMIN_PASSWORD,
                        database='postgres'
                    )
                    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                    admin_cursor = admin_conn.cursor()
                    safe_name = _safe_db_identifier(database_name)
                    admin_cursor.execute(f'DROP DATABASE IF EXISTS "{safe_name}"')
                    admin_cursor.close()
                    admin_conn.close()
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup database {database_name}: {cleanup_error}")
                
                return jsonify({
                    'error': 'User already exists',
                    'message': f'A user with email "{email}" already exists. Please use a different email or create the user separately.'
                }), 409
            
            # Hash password
            password_hash = hash_password(password)
            
            # Create depot manager user
            user_id = uuid.uuid4()
            full_name = contact_person if contact_person else business_name
            
            session.execute(
                text("""
                    INSERT INTO users (id, email, password_hash, full_name, phone, role, tenant_id, is_active, email_verified)
                    VALUES (:id, :email, :password_hash, :full_name, :phone, 'depot', :tenant_id, TRUE, TRUE)
                """),
                {
                    'id': user_id,
                    'email': email,
                    'password_hash': password_hash,
                    'full_name': full_name,
                    'phone': phone,
                    'tenant_id': tenant_id
                }
            )
            
            session.commit()
            session.close()
        except Exception as user_error:
            # Rollback transaction
            session.rollback()
            session.close()
            
            # Try to clean up the database we just created
            try:
                import psycopg2
                from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
                admin_conn = psycopg2.connect(
                    host=Config.PG_ADMIN_HOST,
                    port=Config.CENTRAL_DB_PORT,
                    user=Config.PG_ADMIN_USER,
                    password=Config.PG_ADMIN_PASSWORD,
                    database='postgres'
                )
                admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                admin_cursor = admin_conn.cursor()
                safe_name = _safe_db_identifier(database_name)
                admin_cursor.execute(f'DROP DATABASE IF EXISTS "{safe_name}"')
                admin_cursor.close()
                admin_conn.close()
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup database {database_name}: {cleanup_error}")
            
            logger.error(f"Error creating user: {user_error}", exc_info=True)
            return jsonify({
                'error': 'Failed to create depot user',
                'message': f'Database error while creating user: {str(user_error)}. Please check your database connection and try again.'
            }), 500
        
        return jsonify({
            'message': 'Depot and user account created successfully',
            'tenant': {
                'id': str(tenant.id),
                'business_name': tenant.business_name,
                'email': tenant.email,
                'database_name': tenant.database_name,
                'status': tenant.status,
                'created_at': tenant.created_at.isoformat() if tenant.created_at else None
            },
            'user': {
                'id': str(user_id),
                'email': email,
                'full_name': full_name,
                'role': 'depot'
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Create depot error: {e}", exc_info=True)
        error_message = str(e)
        
        # Provide more helpful error messages
        if 'connection' in error_message.lower() or 'connect' in error_message.lower():
            error_message = 'Database connection failed. Please check your PostgreSQL server is running and credentials are correct.'
        elif 'permission' in error_message.lower() or 'access' in error_message.lower():
            error_message = 'Database permission denied. Please check PostgreSQL user permissions.'
        elif 'duplicate' in error_message.lower() or 'unique' in error_message.lower():
            error_message = 'A depot with this information already exists. Please use different email or registration number.'
        
        return jsonify({
            'error': 'Failed to create depot',
            'message': error_message
        }), 500


@admin_bp.route('/tenants', methods=['GET'])
@require_auth
@require_role('admin')
def list_tenants():
    """List all tenants"""
    try:
        session = CentralDB.get_session()
        
        status = request.args.get('status', 'active')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit
        
        # Get tenants
        result = session.execute(
            text("""
                SELECT id, business_name, registration_number, contact_person,
                    email, phone, address, database_name, status, created_at, updated_at
                FROM tenants
                WHERE status = :status
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {'status': status, 'limit': limit, 'offset': offset}
        )
        tenants = result.fetchall()
        
        # Get total count
        count_result = session.execute(
            text("SELECT COUNT(*) FROM tenants WHERE status = :status"),
            {'status': status}
        )
        total = count_result.scalar()
        
        session.close()
        
        return jsonify({
            'tenants': [{
                'id': str(t.id),
                'business_name': t.business_name,
                'registration_number': t.registration_number,
                'contact_person': t.contact_person,
                'email': t.email,
                'phone': t.phone,
                'address': t.address,
                'database_name': t.database_name,
                'status': t.status,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'updated_at': t.updated_at.isoformat() if t.updated_at else None
            } for t in tenants],
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit
            }
        }), 200
        
    except Exception as e:
        logger.error(f"List tenants error: {e}")
        return jsonify({'error': 'Failed to list tenants', 'message': str(e)}), 500


@admin_bp.route('/tenant/<tenant_id>', methods=['PUT'])
@require_auth
@require_role('admin')
def update_tenant(tenant_id):
    """Update tenant information"""
    try:
        data = request.get_json()
        session = CentralDB.get_session()
        
        # Build update query dynamically
        updates = {}
        allowed_fields = ['business_name', 'contact_person', 'email', 'phone', 'address', 'status']
        for field in allowed_fields:
            if field in data:
                updates[field] = data[field]
        
        if not updates:
            session.close()
            return jsonify({'error': 'No valid fields to update'}), 400
        
        # Update tenant
        set_clause = ', '.join([f"{k} = :{k}" for k in updates.keys()])
        updates['id'] = tenant_id
        
        result = session.execute(
            text(f"""
                UPDATE tenants
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                RETURNING id, business_name, email, status, updated_at
            """),
            updates
        )
        tenant = result.fetchone()
        
        if not tenant:
            session.close()
            return jsonify({'error': 'Depot not found'}), 404
        
        session.commit()
        session.close()
        
        return jsonify({
            'message': 'Depot updated successfully',
            'tenant': {
                'id': str(tenant.id),
                'business_name': tenant.business_name,
                'email': tenant.email,
                'status': tenant.status,
                'updated_at': tenant.updated_at.isoformat() if tenant.updated_at else None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Update depot error: {e}")
        return jsonify({'error': 'Failed to update depot', 'message': str(e)}), 500


@admin_bp.route('/tenant/<tenant_id>', methods=['DELETE'])
@require_auth
@require_role('admin')
def delete_tenant(tenant_id):
    """Permanently delete a tenant and its database"""
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        
        session = CentralDB.get_session()
        
        # Get tenant info including database name
        result = session.execute(
            text("""
                SELECT id, business_name, database_name
                FROM tenants
                WHERE id = :id
            """),
            {'id': tenant_id}
        )
        tenant = result.fetchone()
        
        if not tenant:
            session.close()
            return jsonify({'error': 'Depot not found'}), 404
        
        tenant_db_name = tenant.database_name
        business_name = tenant.business_name
        
        # Delete all users associated with this tenant
        session.execute(
            text("DELETE FROM users WHERE tenant_id = :tenant_id"),
            {'tenant_id': tenant_id}
        )
        
        # Delete the tenant record
        session.execute(
            text("DELETE FROM tenants WHERE id = :id"),
            {'id': tenant_id}
        )
        
        session.commit()
        session.close()
        
        # Drop the tenant database
        try:
            admin_conn_params = {
                'host': Config.PG_ADMIN_HOST,
                'port': Config.CENTRAL_DB_PORT,
                'user': Config.PG_ADMIN_USER,
                'password': Config.PG_ADMIN_PASSWORD,
                'database': 'postgres'  # Connect to postgres database to drop tenant database
            }
            
            admin_conn = psycopg2.connect(**admin_conn_params)
            admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            admin_cursor = admin_conn.cursor()
            
            # Terminate all connections to the tenant database first
            safe_name = _safe_db_identifier(tenant_db_name)
            admin_cursor.execute(
                "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                "FROM pg_stat_activity "
                "WHERE pg_stat_activity.datname = %s "
                "AND pid <> pg_backend_pid()",
                (tenant_db_name,)
            )
            
            # Drop the database
            admin_cursor.execute(f'DROP DATABASE IF EXISTS "{safe_name}"')
        except Exception as db_error:
            logger.error(f"Error dropping tenant database {tenant_db_name}: {db_error}")
            # Continue even if database drop fails - tenant record is already deleted
        
        return jsonify({
            'message': 'Depot deleted successfully. Database and all data have been removed.',
            'tenant': {
                'id': str(tenant.id),
                'business_name': business_name,
                'database_name': tenant_db_name
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Delete depot error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete depot', 'message': str(e)}), 500


@admin_bp.route('/users', methods=['GET'])
@require_auth
@require_role('admin')
def list_users():
    """List all users in the system with full tenant details"""
    try:
        session = CentralDB.get_session()
        
        # Get all users with full tenant details
        result = session.execute(
            text("""
                SELECT u.id, u.email, u.password_hash, u.full_name, u.phone, u.role, u.tenant_id, 
                    u.is_active, u.email_verified, u.last_login, u.created_at, u.updated_at,
                    t.id as tenant_id_full,
                    t.business_name, t.registration_number, t.contact_person, 
                    t.email as tenant_email, t.phone as tenant_phone, t.address,
                    t.database_name, t.status as tenant_status, t.created_at as tenant_created_at
                FROM users u
                LEFT JOIN tenants t ON u.tenant_id = t.id
                ORDER BY u.created_at DESC
            """)
        )
        users = result.fetchall()
        session.close()
        
        return jsonify({
            'users': [{
                'id': str(u.id),
                'email': u.email,
                'full_name': u.full_name,
                'phone': u.phone,
                'role': u.role,
                'tenant_id': str(u.tenant_id) if u.tenant_id else None,
                'tenant_name': u.business_name,
                'is_active': u.is_active,
                'email_verified': u.email_verified,
                'last_login': u.last_login.isoformat() if u.last_login else None,
                'created_at': u.created_at.isoformat() if u.created_at else None,
                'updated_at': u.updated_at.isoformat() if u.updated_at else None,
                # Full tenant details
                'tenant': {
                    'id': str(u.tenant_id_full) if u.tenant_id_full else None,
                    'business_name': u.business_name,
                    'registration_number': u.registration_number,
                    'contact_person': u.contact_person,
                    'email': u.tenant_email,
                    'phone': u.tenant_phone,
                    'address': u.address,
                    'database_name': u.database_name,
                    'status': u.tenant_status,
                    'created_at': u.tenant_created_at.isoformat() if u.tenant_created_at else None
                } if u.tenant_id_full else None
            } for u in users]
        }), 200
        
    except Exception as e:
        logger.error(f"List users error: {e}")
        return jsonify({'error': 'Failed to list users', 'message': str(e)}), 500


@admin_bp.route('/user/<user_id>', methods=['PUT'])
@require_auth
@require_role('admin')
def update_user(user_id):
    """Update user information"""
    try:
        data = request.get_json()
        session = CentralDB.get_session()
        
        # Validate role if provided
        if 'role' in data:
            valid_roles = ['admin', 'depot']
            if data['role'] not in valid_roles:
                session.close()
                return jsonify({'error': f'Invalid role. Only {valid_roles} are allowed'}), 400
        
        # Build update query dynamically
        updates = {}
        allowed_fields = ['email', 'full_name', 'phone', 'role', 'tenant_id', 'is_active']
        for field in allowed_fields:
            if field in data:
                updates[field] = data[field]
        
        if not updates:
            session.close()
            return jsonify({'error': 'No valid fields to update'}), 400
        
        # Update user
        set_clause = ', '.join([f"{k} = :{k}" for k in updates.keys()])
        updates['id'] = user_id
        
        result = session.execute(
            text(f"""
                UPDATE users
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                RETURNING id, email, full_name, role, is_active, updated_at
            """),
            updates
        )
        user = result.fetchone()
        
        if not user:
            session.close()
            return jsonify({'error': 'User not found'}), 404
        
        session.commit()
        session.close()
        
        return jsonify({
            'message': 'User updated successfully',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'is_active': user.is_active,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Update user error: {e}")
        return jsonify({'error': 'Failed to update user', 'message': str(e)}), 500


@admin_bp.route('/user/<user_id>', methods=['DELETE'])
@require_auth
@require_role('admin')
def delete_user(user_id):
    """Delete a user. If it's a depot user, also delete the tenant and its database."""
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        
        session = CentralDB.get_session()
        
        # Check if user exists and get tenant_id if it's a depot user
        user_result = session.execute(
            text("SELECT id, email, role, tenant_id FROM users WHERE id = :id"),
            {'id': user_id}
        )
        user = user_result.fetchone()
        
        if not user:
            session.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Prevent deleting yourself
        current_user_id = request.current_user.get('user_id')
        if str(user.id) == str(current_user_id):
            session.close()
            return jsonify({'error': 'You cannot delete your own account'}), 400
        
        # If this is a depot user with a tenant, delete the entire tenant (which includes all users and database)
        if user.role == 'depot' and user.tenant_id:
            tenant_id = user.tenant_id
            
            # Get tenant info including database name
            tenant_result = session.execute(
                text("""
                    SELECT id, business_name, database_name
                    FROM tenants
                    WHERE id = :id
                """),
                {'id': tenant_id}
            )
            tenant = tenant_result.fetchone()
            
            if tenant:
                tenant_db_name = tenant.database_name
                business_name = tenant.business_name
                
                # Delete all users associated with this tenant
                session.execute(
                    text("DELETE FROM users WHERE tenant_id = :tenant_id"),
                    {'tenant_id': tenant_id}
                )
                
                # Delete the tenant record
                session.execute(
                    text("DELETE FROM tenants WHERE id = :id"),
                    {'id': tenant_id}
                )
                
                session.commit()
                session.close()
                
                # Drop the tenant database
                try:
                    admin_conn_params = {
                        'host': Config.PG_ADMIN_HOST,
                        'port': Config.CENTRAL_DB_PORT,
                        'user': Config.PG_ADMIN_USER,
                        'password': Config.PG_ADMIN_PASSWORD,
                        'database': 'postgres'  # Connect to postgres database to drop tenant database
                    }
                    
                    admin_conn = psycopg2.connect(**admin_conn_params)
                    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                    admin_cursor = admin_conn.cursor()
                    
                    # Terminate all connections to the tenant database first
                    safe_name = _safe_db_identifier(tenant_db_name)
                    admin_cursor.execute(
                        "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                        "FROM pg_stat_activity "
                        "WHERE pg_stat_activity.datname = %s "
                        "AND pid <> pg_backend_pid()",
                        (tenant_db_name,)
                    )
                    
                    # Drop the database
                    admin_cursor.execute(f'DROP DATABASE IF EXISTS "{safe_name}"')
                    admin_cursor.close()
                    admin_conn.close()
                    
                    logger.info(f"Successfully deleted tenant database: {tenant_db_name}")
                    
                except Exception as db_error:
                    logger.error(f"Error dropping tenant database {tenant_db_name}: {db_error}")
                    # Continue even if database drop fails - tenant and user records are already deleted
                
                return jsonify({
                    'message': 'Depot user, tenant, and database deleted successfully',
                    'user': {
                        'id': str(user.id),
                        'email': user.email
                    },
                    'tenant': {
                        'id': str(tenant.id),
                        'business_name': business_name,
                        'database_name': tenant_db_name
                    }
                }), 200
            else:
                # Tenant not found, just delete the user
                session.execute(
                    text("DELETE FROM users WHERE id = :id"),
                    {'id': user_id}
                )
                session.commit()
                session.close()
                
                return jsonify({
                    'message': 'User deleted successfully (tenant was not found)',
                    'user': {
                        'id': str(user.id),
                        'email': user.email
                    }
                }), 200
        else:
            # Not a depot user or no tenant_id, just delete the user
            session.execute(
                text("DELETE FROM users WHERE id = :id"),
                {'id': user_id}
            )
            
            session.commit()
            session.close()
            
            return jsonify({
                'message': 'User deleted successfully',
                'user': {
                    'id': str(user.id),
                    'email': user.email
                }
            }), 200
        
    except Exception as e:
        logger.error(f"Delete user error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete user', 'message': str(e)}), 500


@admin_bp.route('/system-health', methods=['GET'])
@require_auth
@require_role('admin')
def system_health():
    """Get system health status"""
    try:
        # Test central DB connection
        central_db_ok = CentralDB.test_connection()
        
        return jsonify({
            'status': 'healthy' if central_db_ok else 'degraded',
            'database': {
                'central': 'connected' if central_db_ok else 'disconnected'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"System health check error: {e}")
        return jsonify({'error': 'Health check failed', 'message': str(e)}), 500


@admin_bp.route('/profile', methods=['GET'])
@require_auth
@require_role('admin')
def get_admin_profile():
    """Get current admin user profile"""
    try:
        current_user_id = request.current_user.get('user_id')
        session = CentralDB.get_session()
        
        result = session.execute(
            text("""
                SELECT id, email, full_name, phone, role, created_at, last_login
                FROM users
                WHERE id = :user_id AND role = 'admin'
            """),
            {'user_id': current_user_id}
        )
        user = result.fetchone()
        
        if not user:
            session.close()
            return jsonify({'error': 'Admin user not found'}), 404
        
        session.close()
        
        return jsonify({
            'user': {
                'id': str(user.id),
                'email': user.email,
                'full_name': user.full_name,
                'phone': user.phone,
                'role': user.role,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get admin profile error: {e}")
        return jsonify({'error': 'Failed to get profile', 'message': str(e)}), 500


@admin_bp.route('/profile', methods=['PUT'])
@require_auth
@require_role('admin')
def update_admin_profile():
    """Update admin profile information (email, full_name, phone)"""
    try:
        current_user_id = request.current_user.get('user_id')
        data = request.get_json()
        session = CentralDB.get_session()
        
        # Build update query dynamically
        updates = {}
        allowed_fields = ['email', 'full_name', 'phone']
        for field in allowed_fields:
            if field in data:
                updates[field] = data[field]
        
        if not updates:
            session.close()
            return jsonify({'error': 'No valid fields to update'}), 400
        
        # Check if email is being changed and if it's already taken
        if 'email' in updates:
            email_check = session.execute(
                text("SELECT id FROM users WHERE email = :email AND id != :user_id"),
                {'email': updates['email'], 'user_id': current_user_id}
            )
            if email_check.fetchone():
                session.close()
                return jsonify({'error': 'Email already in use'}), 400
        
        # Update user
        set_clause = ', '.join([f"{k} = :{k}" for k in updates.keys()])
        updates['user_id'] = current_user_id
        
        result = session.execute(
            text(f"""
                UPDATE users
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = :user_id AND role = 'admin'
                RETURNING id, email, full_name, phone, role, updated_at
            """),
            updates
        )
        user = result.fetchone()
        
        if not user:
            session.close()
            return jsonify({'error': 'Admin user not found'}), 404
        
        session.commit()
        session.close()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'full_name': user.full_name,
                'phone': user.phone,
                'role': user.role,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Update admin profile error: {e}")
        return jsonify({'error': 'Failed to update profile', 'message': str(e)}), 500


@admin_bp.route('/profile/password', methods=['PUT'])
@require_auth
@require_role('admin')
def change_admin_password():
    """Change admin password"""
    try:
        current_user_id = request.current_user.get('user_id')
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not current_password or not new_password or not confirm_password:
            return jsonify({'error': 'Current password, new password, and confirmation are required'}), 400
        
        if new_password != confirm_password:
            return jsonify({'error': 'New passwords do not match'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400
        
        session = CentralDB.get_session()
        
        # Get current user and verify current password
        from app.utils.auth import verify_password
        result = session.execute(
            text("SELECT id, password_hash FROM users WHERE id = :user_id AND role = 'admin'"),
            {'user_id': current_user_id}
        )
        user = result.fetchone()
        
        if not user:
            session.close()
            return jsonify({'error': 'Admin user not found'}), 404
        
        if not verify_password(current_password, user.password_hash):
            session.close()
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        # Update password
        new_password_hash = hash_password(new_password)
        session.execute(
            text("""
                UPDATE users
                SET password_hash = :password_hash, updated_at = CURRENT_TIMESTAMP
                WHERE id = :user_id AND role = 'admin'
            """),
            {'password_hash': new_password_hash, 'user_id': current_user_id}
        )
        
        session.commit()
        session.close()
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        logger.error(f"Change admin password error: {e}")
        return jsonify({'error': 'Failed to change password', 'message': str(e)}), 500
