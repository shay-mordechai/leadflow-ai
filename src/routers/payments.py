# src/routers/payments.py
import logging
import secrets
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Internal Project Imports
from src.routers.auth import get_current_user
from src.database.session import get_db
from src.database.models import User  # Ensure User model is imported

router = APIRouter()
logger = logging.getLogger("Payments")

# --- Coupon Configuration ---
# Hardcoded for MVP. In production, consider moving to a DB table.
ACTIVE_COUPONS = {
    "LAUNCH2026": {"plan": "premium", "days": 30, "desc": "Launch Special"},
    "VIP_SHAY":   {"plan": "premium", "days": 365, "desc": "Admin Bypass"},
    "YOGA10":     {"plan": "premium", "days": 14,  "desc": "Yoga Teachers Promo"}
}

# --- Pydantic Models ---

class CouponRequest(BaseModel):
    # Security: Added regex pattern to prevent SQL injection or XSS payloads via coupon field
    coupon_code: str = Field(..., min_length=3, max_length=20, pattern="^[A-Z0-9_]+$", description="Alphanumeric coupon code")

class PaymentWebhook(BaseModel):
    """
    Standard structure for receiving payment success signals from external providers 
    (e.g., Morning, iCount, Stripe).
    """
    external_transaction_id: str
    customer_email: str
    amount: float
    status: str  # e.g., "success", "paid"

# --- Routes ---

@router.post("/redeem-coupon")
async def redeem_coupon(
    payload: CouponRequest,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upgrades the user to Premium status immediately if the coupon code is valid.
    This updates the REAL database.
    """
    # 1. Input Sanitization
    code = payload.coupon_code.upper().strip()
    user_id = user.get("user_id")
    
    logger.info(f"User {user_id} attempting to redeem coupon: {code}")

    # 2. Validate Coupon Logic
    if code not in ACTIVE_COUPONS:
        # Security Note: In high-risk environments, consider adding a randomized delay 
        # to prevent timing attacks or brute-force guessing.
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")

    benefit = ACTIVE_COUPONS[code]
    
    # 3. Perform Database Update (Transaction)
    try:
        # Fetch the actual user record from the database
        user_record = db.query(User).filter(User.id == user_id).first()
        
        if not user_record:
            logger.error(f"User ID {user_id} not found in DB during coupon redemption.")
            raise HTTPException(status_code=404, detail="User account not found")

        # Log previous state for auditing
        prev_plan = user_record.plan_type
        
        # Apply Upgrade
        user_record.plan_type = benefit["plan"]
        
        # Save changes
        db.commit()
        db.refresh(user_record)
        
        logger.info(f"✅ COUPON SUCCESS: User {user_id} upgraded ({prev_plan} -> {benefit['plan']}).")

        return {
            "status": "success",
            "message": f"Coupon applied! You are now a {benefit['plan'].title()} member.",
            "plan": user_record.plan_type,
            "desc": benefit["desc"]
        }

    except Exception as e:
        logger.error(f"Database error during coupon redemption: {e}")
        db.rollback() # Ensure DB integrity
        raise HTTPException(status_code=500, detail="Internal server error processing coupon")


@router.post("/webhook/{provider}")
async def payment_provider_webhook(
    provider: str,
    webhook_data: Dict, # Dynamic dict to handle different providers (Morning, Stripe, etc.)
    db: Session = Depends(get_db),
    # Security: Verify the request comes from the real provider using a secret header
    x_signature: Optional[str] = Header(None) 
):
    """
    Generic Webhook Listener for Payment Providers (Morning, iCount, Meshulam).
    When a user pays via Bit/Credit Card, the provider calls this URL.
    """
    logger.info(f"Received Webhook from {provider}. Data: {webhook_data}")

    # TODO: Implement signature verification based on the specific provider documentation.
    # if not verify_signature(x_signature, provider):
    #     raise HTTPException(status_code=403, detail="Invalid Signature")

    # Mock Logic for MVP:
    # We assume the provider sends 'email' and 'status'='success'
    email = webhook_data.get("email") or webhook_data.get("customer_email")
    status = webhook_data.get("status")

    if status != "success":
        logger.warning(f"Payment failed or pending for {email}")
        return {"status": "ignored"}

    # Update User in DB based on Email
    user_record = db.query(User).filter(User.email == email).first()
    if user_record:
        user_record.plan_type = "premium"
        db.commit()
        logger.info(f"💰 PAYMENT RECEIVED: User {email} upgraded to Premium via {provider}.")
        return {"status": "processed"}
    else:
        logger.warning(f"Payment received for unknown email: {email}")
        return {"status": "user_not_found"}