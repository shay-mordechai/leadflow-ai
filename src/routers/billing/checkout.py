# src/routers/billing/checkout.py
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.security.dependencies import get_current_user
from src.database.session import get_db
from src.database.models import User, PlanTier, AuditLog, SubscriptionStatus
from src.services.billing.grow_service import grow_service
from src.security.audit import audit_service
from src.config import settings

router = APIRouter(tags=["Billing - Checkout"])
logger = logging.getLogger("BillingCheckout")

# --- Schemas ---
ACTIVE_COUPONS = {
    "LAUNCH2026": {"plan": "PRO", "days": 30, "desc": "Launch Special"},
    "VIP_SHAY":   {"plan": "PRO", "days": 365, "desc": "Admin Bypass"},
}

class CouponRequest(BaseModel):
    coupon_code: str = Field(..., min_length=3, max_length=20, pattern="^[A-Z0-9_]+$")

# --- Routes ---

@router.post("/create-payment")
async def create_checkout_session(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates a unique Meshulam/Grow payment link for the PRO subscription.
    """
    logger.info(f"Initiating payment session for User: {user.id}")
    
    # 1. Define payment parameters
    amount = 199.00 # Monthly PRO plan cost
    description = "MyLeads AI - PRO Plan Subscription"
    
    # Base URL for redirects (should be the frontend domain)
    base_redirect = settings.BASE_URL.rstrip("/")
    success_url = f"{base_redirect}/dashboard/billing?status=success"
    cancel_url = f"{base_redirect}/dashboard/billing?status=cancelled"

    # 2. Call the Grow Service
    payment_res = await grow_service.create_payment_page(
        amount=amount,
        description=description,
        customer_name=user.name,
        customer_phone=user.assigned_phone_number or "0500000000",
        user_id=str(user.id), # Sent as custom_field_1 to track the user
        success_url=success_url,
        cancel_url=cancel_url
    )

    if payment_res.get("status") == 1:
        return {"payment_url": payment_res.get("url")}
    else:
        raise HTTPException(status_code=500, detail="Failed to initialize payment gateway.")

@router.post("/webhook/grow")
async def grow_payment_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Critical Endpoint: Receives server-to-server confirmation from Meshulam.
    Updates the user subscription to PRO upon successful payment.
    """
    try:
        # Meshulam sends data as standard form-urlencoded
        data = await request.form()
        
        payment_status = data.get("status")
        user_id = data.get("custom_field_1") # We injected this during create_payment_page
        transaction_id = data.get("transaction_id")
        amount = data.get("sum")

        logger.info(f"Received Grow Webhook. Status: {payment_status}, User: {user_id}")

        if str(payment_status) == "1" and user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                # 1. Upgrade User State
                user.plan_tier = PlanTier.PRO
                user.subscription_status = SubscriptionStatus.ACTIVE
                db.flush() # Ensure user updates are tracked before creating the audit log

                # 2. Create Audit Log in the same transaction
                new_log = AuditLog(
                    user_id=str(user.id),
                    action="SUBSCRIPTION_PAID",
                    details={
                        "transaction_id": transaction_id,
                        "amount": amount,
                        "provider": "Grow/Meshulam"
                    }
                )
                db.add(new_log)
                
                # 3. Final atomic commit
                db.commit()
                
                logger.info(f"💰 User {user.email} upgraded to PRO via Grow Webhook. TXN: {transaction_id}")
                return {"status": "success", "message": "Subscription activated."}
            else:
                logger.error(f"Webhook matched unknown User ID: {user_id}")
        
        return {"status": "ignored", "message": "Not a successful transaction or missing user ID."}

    except Exception as e:
        db.rollback()
        logger.error(f"🔥 Webhook Processing Error: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")

@router.post("/redeem-coupon")
async def redeem_coupon(
    payload: CouponRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bypasses payment using an admin coupon code.
    """
    code = payload.coupon_code.upper().strip()
    
    if code not in ACTIVE_COUPONS:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")

    benefit = ACTIVE_COUPONS[code]
    
    try:
        if user.plan_tier == PlanTier.PRO:
             return {"message": "Plan is already PRO", "plan": user.plan_tier.value}

        # 1. Atomic User Upgrade
        user.plan_tier = PlanTier.PRO
        user.subscription_status = SubscriptionStatus.ACTIVE
        db.flush()

        # 2. Create Log within same session to avoid IntegrityErrors
        new_log = AuditLog(
            user_id=str(user.id),
            action="COUPON_REDEEMED",
            details={"coupon_code": code}
        )
        db.add(new_log)
        
        # 3. Single commit for both user and log
        db.commit()
        db.refresh(user)
        
        logger.info(f"✅ COUPON SUCCESS: User {user.id} upgraded to {benefit['plan']}.")

        return {
            "status": "success",
            "message": f"Coupon applied! You are now a {benefit['plan']} member.",
            "plan": user.plan_tier.value,
            "desc": benefit["desc"]
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Database error during coupon redemption: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")