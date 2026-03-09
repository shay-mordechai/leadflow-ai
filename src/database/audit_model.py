# src/database/audit_model.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from src.database.session import Base

class AuditLog(Base):
    """
    Tier 2 Security: Audit Logging.
    Records every critical action performed by users for security and debugging.
    "Who did what, and when?"
    """
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), index=True)
    action = Column(String, nullable=False, index=True) # e.g., "AI_PROMPT_UPDATE", "PAYMENT_SUCCESS"
    details = Column(JSON, nullable=True) # Store metadata like old_value, new_value, ip_address
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<AuditLog(action={self.action}, user_id={self.user_id})>"