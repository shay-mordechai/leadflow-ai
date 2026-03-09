# src/security/audit.py
import logging
from sqlalchemy.orm import Session
from src.database.audit_model import AuditLog

logger = logging.getLogger("AuditSystem")

class AuditService:
    """
    Tier 2 Security: Audit Logging Service.
    Helper service to record events in the AuditLog table.
    Tracks critical user actions for security compliance and debugging.
    """
    @staticmethod
    def log(db: Session, user_id: str, action: str, details: dict = None):
        try:
            new_log = AuditLog(
                user_id=user_id,
                action=action,
                details=details
            )
            db.add(new_log)
            db.commit()
            
            # Also emit to structured logs for CloudWatch/ELK observability
            logger.info(f"AUDIT_EVENT: {action}", extra={
                "user_id": user_id,
                "action": action,
                "details": details
            })
        except Exception as e:
            # We use logger.error but don't raise to ensure 
            # audit failures don't crash the main business flow
            logger.error(f"Failed to save Audit Log: {e}")

audit_service = AuditService()