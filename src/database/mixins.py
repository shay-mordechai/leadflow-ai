# Professional English Comment:
# Multi-tenancy mixin with deferred import to prevent circular dependencies.
# Ensures data isolation by filtering queries based on the current context.

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declared_attr, Session

class TenantAwareMixin:
    """
    Mixin to ensure every model belongs to a tenant and
    queries are automatically filtered by the current tenant context.
    """

    @declared_attr
    def tenant_id(cls):
        # All tables using this mixin must have a tenant_id linked to tenants table
        return Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)

    @classmethod
    def get_query(cls, session: Session):
        """
        Returns a query object pre-filtered by the current tenant.
        This prevents accidental data leaks between tenants.
        """
        # Professional English Comment:
        # Deferred import inside the method breaks the circular loop between 
        # models -> mixins -> security -> models.
        from src.security.tenant import get_tenant_id
        
        current_tenant = get_tenant_id()
        return session.query(cls).filter(cls.tenant_id == current_tenant)