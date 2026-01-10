from contextvars import ContextVar
from fastapi import Security, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
from src.database.session import get_db
import uuid

# Context variable to hold the tenant_id for the current request
_tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id", default=None)

api_key_header = APIKeyHeader(name="X-Tenant-API-Key", auto_error=True)

def set_tenant_id(tenant_id: str):
    """Sets the tenant ID in the context var."""
    return _tenant_id_ctx.set(str(tenant_id))

def reset_tenant_id(token):
    """Resets the context var to previous state."""
    _tenant_id_ctx.reset(token)

def get_tenant_id() -> str:
    """
    Retrieves the current tenant ID.
    Raises an error if accessed outside of a secured context.
    """
    tid = _tenant_id_ctx.get()
    if tid is None:
        # Critical Security Check: accessing DB without tenant context
        raise RuntimeError("Security Violation: Attempted to access tenant-scoped data without context.")
    return tid

async def get_current_tenant_id(
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db)
) -> str:
    """
    Dependency that validates the API Key and sets the ContextVar.
    Used by routers to enforce authentication.
    """
    # Deferred import to avoid circular dependency
    from src.database.models import Tenant
    from src.security.hashing import verify_hash

    # We fetch all active tenants and check hashes
    # (In high scale, we would cache this mapping in Redis)
    tenants = db.query(Tenant).filter(Tenant.is_active == True).all()

    authorized_tenant = None
    for t in tenants:
        if verify_hash(api_key, t.api_key_hash):
            authorized_tenant = t
            break

    if not authorized_tenant:
        # Generic error message to prevent enumeration
        raise HTTPException(status_code=403, detail="Invalid Credentials")

    # Set the ContextVar for the request duration
    set_tenant_id(str(authorized_tenant.id))

    return str(authorized_tenant.id)
