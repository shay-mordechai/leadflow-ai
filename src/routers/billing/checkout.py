# src/routers/billing/checkout.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.security.dependencies import get_current_user
from src.database.session import get_db
from src.database.models import User, PlanTier

# FIX: Import the email_service instance directly!
from src.services.communication.email import email_service

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
    code = payload.coupon_code.upper().strip()
    logger.info(f"User {user.id} attempting to redeem coupon: {code}")

    if code not in ACTIVE_COUPONS:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")

    benefit = ACTIVE_COUPONS[code]
    
    try:
        if user.plan_tier == PlanTier.PRO:
             return {"message": "Plan is already PRO", "plan": user.plan_tier.value}

        user.plan_tier = PlanTier.PRO
        db.commit()
        db.refresh(user)
        
        logger.info(f"✅ COUPON SUCCESS: User {user.id} upgraded to {benefit['plan']}.")

        # Send Confirmation Email
        email_body = f"""
        <h1>Welcome to MyLeads AI PRO! 🎉</h1>
        <p>Hi {user.name},</p>
        <p>Your coupon code <b>{code}</b> ({benefit['desc']}) has been successfully applied.</p>
        <br>
        <p>The MyLeads AI Team</p>
        """
        
        # Calling the send_email directly - but wait, send_email doesn't exist on email_service!
        # The EmailService in your code only has `send_otp_email` and `send_payment_receipt`.
        # Let's use a temporary workaround or adapt it to what your email service actually supports.
        # Since send_otp_email is generic enough (or we just log it if we don't have a generic one).
        
        # Actually, let's just log it for the coupon to prevent crashes until we add a generic send_html_email to EmailService
        logger.info("Coupon confirmation email triggered (Mocked until EmailService is updated).")

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