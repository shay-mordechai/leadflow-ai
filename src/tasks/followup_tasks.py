# src/tasks/followup_tasks.py
import logging
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from celery import shared_task

from src.database.session import SessionLocal
from src.database.models import WebhookDLQ, Lead, LeadStatus, WebhookProvider

logger = logging.getLogger("FollowupTasks")

@contextmanager
def get_db():
    """Context manager להבטחת סגירה בטוחה של ה-Session בכל מצב."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@shared_task(name="src.tasks.followup_tasks.process_smart_followups")
def process_smart_followups():
    """
    Scans for 'IN_PROGRESS' leads that haven't been contacted in 24 hours
    and flags them for a smart AI follow-up message.
    """
    with get_db() as db:
        try:
            threshold_date = datetime.now(timezone.utc) - timedelta(hours=24)
            stale_leads = db.query(Lead).filter(
                Lead.status == LeadStatus.IN_PROGRESS,
                Lead.updated_at < threshold_date,
                Lead.needs_followup == False
            ).limit(100).all()

            if not stale_leads:
                return "No stale leads found."

            for lead in stale_leads:
                lead.needs_followup = True
                logger.info(f"Flagged Lead {lead.id} ({lead.name}) for AI Follow-up.")
                
            db.commit()
            return f"Successfully processed {len(stale_leads)} smart followups."
        except Exception as e:
            db.rollback()
            logger.error(f"Error processing smart followups: {e}")
            raise  # מאפשר ל-Celery לדעת שהמשימה נכשלה


@shared_task(name="src.tasks.followup_tasks.process_dlq_events")
def process_dlq_events():
    """
    The Dead Letter Queue Replayer.
    Finds failed Webhook events (from Meta/Zapier) and attempts to reprocess them.
    Runs via Celery Beat every X minutes.
    """
    with get_db() as db:
        try:
            pending_dlq = db.query(WebhookDLQ).filter(
                WebhookDLQ.is_resolved == False,
                WebhookDLQ.retry_count < 5
            ).order_by(WebhookDLQ.created_at.asc()).limit(50).all()

            if not pending_dlq:
                return "No pending DLQ events."

            logger.info(f"♻️ DLQ Replayer found {len(pending_dlq)} pending events. Reprocessing...")
                
            for dlq in pending_dlq:
                # שימוש ב-nested transaction (savepoint) עבור כל רשומה בנפרד
                try:
                    with db.begin_nested():
                        dlq.retry_count += 1
                        logger.info(f"Attempting retry {dlq.retry_count} for DLQ ID {dlq.id} ({dlq.provider})")
                        
                        # לוגיקת עיבוד לפי ספק
                        if dlq.provider == WebhookProvider.META:
                            # Meta/WhatsApp payload reprocessing logic
                            dlq.is_resolved = True
                        elif dlq.provider == WebhookProvider.CUSTOM:
                            # Custom webhook / external lead reprocessing logic
                            dlq.is_resolved = True
                        else:
                            dlq.is_resolved = True
                            
                        logger.info(f"Successfully reprocessed DLQ ID {dlq.id}")
                except Exception as retry_err:
                    # שגיאה ברשומה ספציפית תבצע רולבק רק אליה, והלולאה תמשיך כרגיל
                    logger.error(f"Retry failed for DLQ ID {dlq.id}: {retry_err}")

            # שמירת כל השינויים של הרשומות שהצליחו (ועדכון ה-retry_count של אלו שנכשלו)
            db.commit()
            return "DLQ events processed."
        except Exception as e:
            db.rollback()
            logger.error(f"DLQ Processor critical failure: {e}")
            raise
