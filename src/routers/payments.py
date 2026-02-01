# src/routers/payments.py
import logging
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

from src.routers.auth import get_current_user
# Placeholder for DB access or User Service.
# In a real ORM scenario, we would import the User model and DB session here.

router = APIRouter()
logger = logging.getLogger("Payments")

# --- Coupon Definitions (Hardcoded for MVP) ---
# Future Improvement: Move this to a 'coupons' table in the database.
ACTIVE_COUPONS = {
    "LAUNCH2026": {"plan": "premium", "days": 30, "desc": "Launch Special"},
    "VIP_SHAY":   {"plan": "premium", "days": 365, "desc": "Admin Bypass"},
    "YOGA10":     {"plan": "premium", "days": 14,  "desc": "Yoga Teachers Promo"}
}

class CouponRequest(BaseModel):
    # Security: Added validation to prevent injection or long string attacks (SAST)
    coupon_code: str = Field(..., min_length=3, max_length=20, pattern="^[A-Z0-9_]+$", description="Alphanumeric coupon code")

@router.post("/redeem-coupon")
async def redeem_coupon(
    payload: CouponRequest,
    user: Dict = Depends(get_current_user)
):
    """
    Upgrades the user to Premium status if the coupon code is valid.
    """
    # Input sanitization
    code = payload.coupon_code.upper().strip()
    user_id = user.get("user_id")
    
    logger.info(f"User {user_id} attempting to redeem coupon: {code}")

    # 1. Validate Coupon
    if code not in ACTIVE_COUPONS:
        # Security Note: In a high-security env, add a small sleep() here to mitigate timing attacks.
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")

    benefit = ACTIVE_COUPONS[code]
    
    # 2. Execute Upgrade (Simulation)
    # TODO: Connect this to your actual DB repository to update 'users.plan_type'.
    # Example: await user_repo.update_plan(user_id, benefit["plan"])
    
    logger.info(f"✅ COUPON VALID! Upgrading user {user_id} to {benefit['plan']}")
    
    return {
        "status": "success",
        "message": f"Coupon applied! You are now a {benefit['plan']} member.",
        "plan": benefit["plan"],
        "valid_for_days": benefit["days"]
    }