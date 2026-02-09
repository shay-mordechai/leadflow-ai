# src/routers/billing/checkout.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Internal Project Imports
# Updated import to match the new security structure
from src.security.dependencies import get_current_user
from src.database.session import get_db
from src.database.models import User, PlanTier

router = APIRouter(tags=["Billing - Checkout"])
logger = logging.getLogger("BillingCheckout")

# --- Configuration ---
# Hardcoded coupons for now. Ideally, move this to a DB table later.
ACTIVE_COUPONS = {
    "LAUNCH2026": {"plan": "PRO", "days": 30, "desc": "Launch Special"},
    "VIP_SHAY":   {"plan": "PRO", "days": 365, "desc": "Admin Bypass"},
}

# --- Models ---
class CouponRequest(BaseModel):
    coupon_code: str = Field(..., min_length=3, max_length=20, pattern="^[A-Z0-9_]+$")

# --- Routes ---

@router.post("/redeem-coupon")
async def redeem_coupon(
    payload: CouponRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upgrades the user to Premium status immediately if the coupon code is valid.
    """
    code = payload.coupon_code.upper().strip()
    
    logger.info(f"User {user.id} attempting to redeem coupon: {code}")

    if code not in ACTIVE_COUPONS:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")

    benefit = ACTIVE_COUPONS[code]
    
    try:
        # Check current status
        if user.plan_tier == PlanTier.PRO:
             return {"message": "Plan is already PRO", "plan": user.plan_tier}

        # Apply Upgrade
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