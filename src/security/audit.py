# src/security/audit.py
import logging
import re
from typing import Any
from sqlalchemy.orm import Session

# FIXED: מייבא מהקובץ המאוחד החדש ולא מהקובץ הישן שנמחק
from src.database.models import AuditLog

logger = logging.getLogger("AuditSystem")
_ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_audit_value(value: Any) -> Any:
    """Strip line separators and terminal controls from structured audit values."""
    if isinstance(value, str):
        return _CONTROL_CHARACTERS.sub("", _ANSI_ESCAPE.sub("", value))
    if isinstance(value, dict):
        return {
            _sanitize_audit_value(key) if isinstance(key, str) else key: _sanitize_audit_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_audit_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_audit_value(item) for item in value)
    return value

class AuditService:
    """
    Tier 2 Security: Audit Logging Service.
    Helper service to record events in the AuditLog table.
    Tracks critical user actions for security compliance and debugging.
    """
    @staticmethod
    def log(db: Session, user_id: str, action: str, details: dict = None):
        try:
            safe_action = _sanitize_audit_value(action)
            safe_details = _sanitize_audit_value(details or {})
            safe_user_id = _sanitize_audit_value(str(user_id))
            new_log = AuditLog(
                user_id=safe_user_id,
                action=safe_action,
                details=safe_details
            )
            db.add(new_log)
            # אנו משתמשים ב-flush במקום commit.
            # כך, מי שקרא לפונקציה (למשל ה-Webhook) אחראי על ה-commit הסופי,
            # והמידע לא נשמר חצי-כוח במקרה של שגיאה בהמשך התהליך.
            db.flush()
            
            # Also emit to structured logs for CloudWatch/ELK observability
            logger.info(f"AUDIT_EVENT: {safe_action}", extra={
                "user_id": safe_user_id,
                "action": safe_action,
                "details": safe_details
            })
        except Exception as e:
            # We use logger.error but don't raise to ensure 
            # audit failures don't crash the main business flow
            logger.error(f"Failed to save Audit Log: {e}")

audit_service = AuditService()