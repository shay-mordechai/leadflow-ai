# src/routers/billing/checkout.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.security.dependencies import get_current_user
from src.database.session import get_db
from src.database.models import User, PlanTier
from src.services.communication.email import email_service # NEW: Import Email Service

router = APIRouter(tags=["Billing - Checkout"])
logger = logging.getLogger("BillingCheckout")

ACTIVE_COUPONS = {
    "LAUNCH2026": {"plan": "PRO", "days": 30, "desc": "Launch Special"},
    "VIP_SHAY":   {"plan": "PRO", "days": 365, "desc": "Admin Bypass"},
}

class CouponRequest(BaseModel):
    coupon_code: str = Field(..., min_length=3, max_length=20, pattern="^[A-Z0-9_]+$")

@router.post("/redeem-coupon")
async def redeem_coupon(
    payload: CouponRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upgrades the user to Premium status immediately if the coupon code is valid.
    Sends a confirmation email.
    """
    code = payload.coupon_code.upper().strip()
    logger.info(f"User {user.id} attempting to redeem coupon: {code}")

    if code not in ACTIVE_COUPONS:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")

    benefit = ACTIVE_COUPONS[code]
    
    try:
        if user.plan_tier == PlanTier.PRO:
             return {"message": "Plan is already PRO", "plan": user.plan_tier.value}

        # Apply Upgrade
        user.plan_tier = PlanTier.PRO
        db.commit()
        db.refresh(user)
        
        logger.info(f"✅ COUPON SUCCESS: User {user.id} upgraded to {benefit['plan']}.")

        # --- NEW: Send Confirmation Email ---
        email_body = f"""
        <h1>Welcome to MyLeads AI PRO! 🎉</h1>
        <p>Hi {user.name},</p>
        <p>Your coupon code <b>{code}</b> ({benefit['desc']}) has been successfully applied.</p>
        <p>You now have full access to premium features, including purchasing virtual phone numbers and unlimited AI voice processing.</p>
        <br>
        <p>Best regards,<br>The MyLeads AI Team</p>
        """
        await email_service.send_email(
            to_email=user.email,
            subject="Welcome to MyLeads AI PRO! 🚀",
            html_content=email_body
        )

        return {
            "status": "success",
            "message": f"Coupon applied! You are now a {benefit['plan']} member.",
            "plan": user.plan_tier.value,
            "desc": benefit["desc"]
        }

    except Exception as e:
        logger.error(f"Database error during coupon redemption: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")