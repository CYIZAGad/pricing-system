"""
Tenant model for central database
"""

from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime


class Tenant:
    """
    Tenant model - represents tenants table in central database
    Note: This is a model definition. The actual table should exist in the imported DB.
    """
    
    __tablename__ = 'tenants'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_name = Column(String(255), nullable=False)
    registration_number = Column(String(100), unique=True)
    contact_person = Column(String(255))
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50))
    address = Column(String(500))
    database_name = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(20), default='active')  # 'active', 'inactive', 'suspended'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def from_dict(data):
        """Create tenant dict from data"""
        return {
            'id': data.get('id'),
            'business_name': data.get('business_name'),
            'registration_number': data.get('registration_number'),
            'contact_person': data.get('contact_person'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'address': data.get('address'),
            'database_name': data.get('database_name'),
            'status': data.get('status', 'active'),
            'created_at': data.get('created_at'),
            'updated_at': data.get('updated_at')
        }
