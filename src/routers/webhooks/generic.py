# src/routers/webhooks/generic.py
import logging
from typing import Dict, Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import User, PlanTier

router = APIRouter(tags=["Webhooks - Generic"])
logger = logging.getLogger("GenericWebhook")

@router.post("/generic-provider")
async def payment_provider_webhook(
    webhook_data: Dict, 
    db: Session = Depends(get_db),
    x_signature: Optional[str] = Header(None) 
):
    """
    Generic Webhook Listener for fallback Payment Providers.
    """
    logger.info(f"Received Generic Webhook. Data: {webhook_data}")

    email = webhook_data.get("email") or webhook_data.get("customer_email")
    status = webhook_data.get("status")

    if status != "success":
        logger.warning(f"Payment failed or pending for {email}")
        return {"status": "ignored"}

    user_record = db.query(User).filter(User.email == email).first()
    
    if user_record:
        user_record.plan_tier = PlanTier.PRO
        db.commit()
        logger.info(f"💰 PAYMENT RECEIVED: User {email} upgraded to Premium.")
        return {"status": "processed"}
    else:
        logger.warning(f"Payment received for unknown email: {email}")
        return {"status": "user_not_found"}