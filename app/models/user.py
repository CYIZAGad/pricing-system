"""
User model for central database
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime


class User:
    """
    User model - represents users table in central database
    Note: This is a model definition. The actual table should exist in the imported DB.
    """
    
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    phone = Column(String(50))
    role = Column(String(50), nullable=False, index=True)  # 'admin', 'depot_manager', 'depot_staff', 'pharmacy'
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def from_dict(data):
        """Create user dict from data"""
        return {
            'id': data.get('id'),
            'email': data.get('email'),
            'full_name': data.get('full_name'),
            'phone': data.get('phone'),
            'role': data.get('role'),
            'tenant_id': data.get('tenant_id'),
            'is_active': data.get('is_active', True),
            'email_verified': data.get('email_verified', False),
            'last_login': data.get('last_login'),
            'created_at': data.get('created_at'),
            'updated_at': data.get('updated_at')
        }
