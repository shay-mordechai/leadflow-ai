# src/tasks/billing_tasks.py
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import sentry_sdk

from src.database.session import SessionLocal
from src.database.models import User, PlanTier, SubscriptionStatus

logger = logging.getLogger("BillingTasks")

def enforce_trial_expirations():
    """
    Business Logic: Scans for users whose 14-day trial has expired.
    Downgrades their account to STARTER to prevent free abuse of AI resources.
    This runs daily as a background cron job.
    """
    logger.info("⏳ Starting Trial Expiration Enforcement Job...")
    
    # We must manually open a DB session since this runs outside FastAPI's request cycle
    db: Session = SessionLocal()
    try:
        # Calculate the cutoff date (14 days ago)
        expiration_cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        
        # Find users who are still on TRIAL and their creation date is older than 14 days
        expired_users = db.query(User).filter(
            User.subscription_status == SubscriptionStatus.TRIAL,
            User.created_at < expiration_cutoff
        ).all()
        
        if not expired_users:
            logger.info("✅ No expired trials found today.")
            return

        downgraded_count = 0
        for user in expired_users:
            # SECURITY & BUSINESS: Downgrade user to STARTER and mark as PAST_DUE
            user.plan_tier = PlanTier.STARTER
            user.subscription_status = SubscriptionStatus.PAST_DUE
            
            # (Future step: Send an automated email here using SendGrid/Brevo)
            logger.info(f"📉 Downgraded User ID {user.id} ({user.email}) - Trial Expired.")
            downgraded_count += 1
            
        db.commit()
        logger.info(f"🎯 Successfully downgraded {downgraded_count} users to prevent resource abuse.")
        
    except Exception as e:
        db.rollback()
        logger.error(f"🔥 Error in enforce_trial_expirations: {e}")
        sentry_sdk.capture_exception(e) # Send alert to CTO immediately
    finally:
        db.close() # CRITICAL: Always close the DB session to prevent memory leaks