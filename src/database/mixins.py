# src/database/mixins.py
# Multi-tenancy mixin with cross-database support.
# Uses a custom GUID type to ensure compatibility between SQLite and PostgreSQL.

from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import declared_attr, Session
# Import the GUID helper from your models to ensure consistent ID handling
from src.database.models import GUID

class TenantAwareMixin:
    """
    Mixin to ensure data isolation across the platform. 
    Every model inheriting from this mixin will be tied to a specific tenant.
    """

    @declared_attr
    def tenant_id(cls):
        """
        Database-agnostic tenant identifier.
        Linked to the 'tenants' table via a foreign key.
        """
        return Column(GUID(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    @classmethod
    def get_query(cls, session: Session):
        """
        Automatic query filtering based on the active tenant context.
        This serves as a security layer to prevent cross-tenant data leakage.
        """
        # Professional English Comment:
        # Deferred import is used here to resolve circular dependency issues 
        # between the security layer and the database models.
        from src.security.tenant import get_tenant_id
        
        current_tenant = get_tenant_id()
        return session.query(cls).filter(cls.tenant_id == current_tenant)