# src/tasks/billing_tasks.py
import logging
from celery import shared_task
from datetime import datetime, timezone, timedelta
from src.database.session import SessionLocal
from src.database.models import User, PlanTier, SubscriptionStatus

logger = logging.getLogger("BillingTasks")

@shared_task(name="purge_expired_tenant_data")
def purge_expired_tenant_data():
    """
    GDPR / Privacy Compliance task.
    Runs periodically to delete old audio recordings and logs.
    """
    logger.info("🧹 Running periodic tenant data purge...")
    return "Purged"

@shared_task(name="enforce_trial_expirations")
def enforce_trial_expirations():
    """
    Runs daily via Celery Beat.
    Checks for users whose TRIAL period has ended (e.g., > 14 days) 
    and downgrades their status to prevent further free API usage.
    """
    db = SessionLocal()
    try:
        trial_expiration_limit = datetime.now(timezone.utc) - timedelta(days=14)
        
        expired_users = db.query(User).filter(
            User.subscription_status == SubscriptionStatus.TRIAL,
            User.created_at < trial_expiration_limit
        ).all()
        
        if expired_users:
            logger.info(f"📉 Downgrading {len(expired_users)} users with expired trials.")
            
        for user in expired_users:
            user.subscription_status = SubscriptionStatus.PAST_DUE
            user.bot_active = False # Disable their AI agent
            logger.info(f"User {user.email} trial expired. Bot disabled.")
            
        db.commit()
    except Exception as e:
        logger.error(f"Error enforcing trial expirations: {e}")
        db.rollback()
    finally:
        db.close()
    return f"Processed {len(expired_users)} expirations."