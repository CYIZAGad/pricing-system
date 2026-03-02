"""
Audit Log model for central database
"""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime


class AuditLog:
    """
    AuditLog model - represents audit_logs table in central database
    Note: This is a model definition. The actual table should exist in the imported DB.
    """
    
    __tablename__ = 'audit_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # 'login', 'upload', 'download', etc.
    resource_type = Column(String(50))  # 'price_list', 'medicine', etc.
    resource_id = Column(UUID(as_uuid=True))
    details = Column(JSONB)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    @staticmethod
    def from_dict(data):
        """Create audit log dict from data"""
        return {
            'id': data.get('id'),
            'user_id': data.get('user_id'),
            'tenant_id': data.get('tenant_id'),
            'action': data.get('action'),
            'resource_type': data.get('resource_type'),
            'resource_id': data.get('resource_id'),
            'details': data.get('details'),
            'ip_address': data.get('ip_address'),
            'user_agent': data.get('user_agent'),
            'created_at': data.get('created_at')
        }
