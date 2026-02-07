# src/routers/payments.py
import logging
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Internal Project Imports
from src.routers.auth import get_current_user
from src.database.session import get_db
from src.database.models import User, PlanTier  # Ensure User model is imported

router = APIRouter()
logger = logging.getLogger("Payments")

# --- Coupon Configuration ---
ACTIVE_COUPONS = {
    "LAUNCH2026": {"plan": "PRO", "days": 30, "desc": "Launch Special"},
    "VIP_SHAY":   {"plan": "PRO", "days": 365, "desc": "Admin Bypass"},
}

# --- Pydantic Models ---

class CouponRequest(BaseModel):
    coupon_code: str = Field(..., min_length=3, max_length=20, pattern="^[A-Z0-9_]+$")

class PaymentWebhook(BaseModel):
    external_transaction_id: str
    customer_email: str
    amount: float
    status: str 

# --- Routes ---

@router.post("/redeem-coupon")
async def redeem_coupon(
    payload: CouponRequest,
    user: User = Depends(get_current_user), # Type hint updated to User model
    db: Session = Depends(get_db)
):
    """
    Upgrades the user to Premium status immediately if the coupon code is valid.
    """
    code = payload.coupon_code.upper().strip()
    
    # FIX: Access ID directly from the ORM object, not as a dict
    logger.info(f"User {user.id} attempting to redeem coupon: {code}")

    if code not in ACTIVE_COUPONS:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")

    benefit = ACTIVE_COUPONS[code]
    
    try:
        # Check current status
        if user.plan_tier == PlanTier.PRO:
             return {"message": "Plan is already PRO"}

        # Apply Upgrade (Using the correct field name from models.py)
        user.plan_tier = PlanTier.PRO
        
        # Save changes
        db.commit()
        db.refresh(user)
        
        logger.info(f"✅ COUPON SUCCESS: User {user.id} upgraded to {benefit['plan']}.")

        return {
            "status": "success",
            "message": f"Coupon applied! You are now a {benefit['plan']} member.",
            "plan": user.plan_tier,
            "desc": benefit["desc"]
        }

    except Exception as e:
        logger.error(f"Database error during coupon redemption: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/webhook/{provider}")
async def payment_provider_webhook(
    provider: str,
    webhook_data: Dict, 
    db: Session = Depends(get_db),
    x_signature: Optional[str] = Header(None) 
):
    """
    Generic Webhook Listener for Payment Providers.
    Simulates sending a receipt email upon success.
    """
    logger.info(f"Received Webhook from {provider}. Data: {webhook_data}")

    email = webhook_data.get("email") or webhook_data.get("customer_email")
    status = webhook_data.get("status")

    if status != "success":
        logger.warning(f"Payment failed or pending for {email}")
        return {"status": "ignored"}

    user_record = db.query(User).filter(User.email == email).first()
    
    if user_record:
        # 1. Upgrade User
        user_record.plan_tier = PlanTier.PRO
        db.commit()
        
        # 2. Simulate Receipt Email (Log only for now)
        logger.info(f"📧 [MOCK EMAIL] Sending Payment Receipt to {email} via SendGrid/AWS SES.")
        logger.info(f"💰 PAYMENT RECEIVED: User {email} upgraded to Premium via {provider}.")
        
        return {"status": "processed", "receipt_sent": True}
    else:
        logger.warning(f"Payment received for unknown email: {email}")
        return {"status": "user_not_found"}