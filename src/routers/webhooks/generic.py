# src/routers/webhooks/generic.py
import logging
import hmac
from typing import Dict, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

# Internal imports
from src.database.session import get_db
from src.database.models import User, PlanTier
from src.config import settings

router = APIRouter(tags=["Webhooks - Generic"])
logger = logging.getLogger("GenericWebhook")

@router.post("/generic-provider")
async def payment_provider_webhook(
    webhook_data: Dict, 
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-Internal-Webhook-Key") 
):
    """
    Generic Webhook Listener for fallback Payment Providers.
    
    SECURITY:
    - Implements API Key verification via 'X-Internal-Webhook-Key' header.
    - Prevents unauthorized plan upgrades.
    """
    
    # 1. SECURITY: Verify Internal API Key
    # Ensure settings.INTERNAL_WEBHOOK_SECRET is set to a long, random string in your .env
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.INTERNAL_WEBHOOK_SECRET):
        logger.error("❌ UNAUTHORIZED: Generic Webhook called with invalid or missing API Key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized access"
        )

    logger.info(f"Received Authenticated Generic Webhook. Processing data...")

    # 2. Extract Data
    email = webhook_data.get("email") or webhook_data.get("customer_email")
    payment_status = webhook_data.get("status")

    if not email:
        logger.warning("Generic Webhook missing email field.")
        return {"status": "error", "message": "Email is required"}

    # 3. Check Payment Status
    if payment_status != "success":
        logger.warning(f"Payment failed or pending for {email}. Status: {payment_status}")
        return {"status": "ignored", "reason": "payment_not_successful"}

    # 4. Process Upgrade
    # Normalize email to prevent mismatch issues
    user_record = db.query(User).filter(User.email == email.lower()).first()
    
    if user_record:
        if user_record.plan_tier != PlanTier.PRO:
            user_record.plan_tier = PlanTier.PRO
            db.commit()
            logger.info(f"💰 PAYMENT VERIFIED: User {email} upgraded to PRO via Generic Webhook.")
            return {"status": "processed", "user": email, "new_plan": "PRO"}
        else:
            logger.info(f"User {email} is already on PRO plan.")
            return {"status": "no_action_needed", "reason": "already_pro"}
    else:
        logger.error(f"Verified payment received for unknown email: {email}")
        return {"status": "user_not_found"}