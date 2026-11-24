# src/routers/billing/checkout.py
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config import settings
from src.database.models import AuditLog, PlanTier, SubscriptionStatus, User
from src.database.session import get_db
from src.security.dependencies import get_current_user
from src.services.billing.grow_service import grow_service

router = APIRouter(tags=["Billing - Checkout"])
logger = logging.getLogger("BillingCheckout")

PLAN_BASE_PRICES_ILS: dict[str, float] = {
    "STARTER": 99.00,
    "PRO": 199.00,
}

# Supports both partial percentage discounts (1..99) and full cost-zeroing coupons (100)
ACTIVE_COUPONS: dict[str, dict] = {
    "FREE100": {
        "plan": "PRO",
        "discount_percent": 100,
        "days": 30,
        "desc": "100% Free Trial Upgrade",
    },
    "LAUNCH2026": {
        "plan": "PRO",
        "discount_percent": 100,
        "days": 30,
        "desc": "Launch Special (100% Off)",
    },
    "VIP_SHAY": {"plan": "PRO", "discount_percent": 100, "days": 365, "desc": "VIP Full Access"},
    "SAVE50": {"plan": "PRO", "discount_percent": 50, "days": 30, "desc": "50% Off First Month"},
    "STARTER50": {
        "plan": "STARTER",
        "discount_percent": 50,
        "days": 30,
        "desc": "50% Off Starter Plan",
    },
}


class CouponRequest(BaseModel):
    coupon_code: str = Field(..., min_length=3, max_length=24, pattern="^[A-Za-z0-9_-]+$")


class CheckoutRequest(BaseModel):
    plan: str = Field(default="PRO", pattern="^(STARTER|PRO)$")
    coupon_code: str | None = Field(default=None, min_length=3, max_length=24)


def _calculate_discounted_price(
    target_plan: str, coupon_code: str | None
) -> tuple[float, float, dict | None]:
    base_price = PLAN_BASE_PRICES_ILS.get(target_plan.upper(), 199.00)
    if not coupon_code:
        return base_price, base_price, None

    normalized = coupon_code.upper().strip()
    benefit = ACTIVE_COUPONS.get(normalized)
    if not benefit:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")

    discount_pct = int(benefit.get("discount_percent", 100))
    final_price = round(max(0.0, base_price * (100 - discount_pct) / 100.0), 2)
    return base_price, final_price, benefit


@router.post("/create-payment")
async def create_checkout_session(
    payload: CheckoutRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a Meshulam/Grow payment link for STARTER or PRO, applying any valid coupon discount.
    If a 100% coupon reduces cost to 0, upgrades immediately without payment gateway redirect.
    """
    target_plan = (payload.plan if payload else "PRO").upper()
    coupon_code = payload.coupon_code.upper().strip() if (payload and payload.coupon_code) else None

    base_price, final_price, benefit = _calculate_discounted_price(target_plan, coupon_code)
    logger.info(
        f"Initiating checkout for User {user.id}: plan={target_plan}, base={base_price}, final={final_price}"
    )

    if final_price <= 0.0:
        tier_enum = PlanTier.PRO if target_plan == "PRO" else PlanTier.STARTER
        user.plan_tier = tier_enum
        user.subscription_status = SubscriptionStatus.ACTIVE
        db.flush()
        db.add(
            AuditLog(
                user_id=str(user.id),
                action="COUPON_ZERO_COST_ACTIVATION",
                details={"coupon_code": coupon_code, "plan": tier_enum.value, "final_price": 0.0},
            )
        )
        db.commit()
        db.refresh(user)
        return {
            "status": "activated",
            "payment_required": False,
            "original_price": base_price,
            "final_price": 0.0,
            "plan": user.plan_tier.value,
            "message": "Coupon reduced cost to 0 ILS. Subscription activated immediately.",
        }

    description = f"My-Leads AI - {target_plan} Plan Subscription"
    if coupon_code:
        description += f" (Coupon: {coupon_code})"

    base_redirect = settings.BASE_URL.rstrip("/")
    success_url = f"{base_redirect}/dashboard/billing?status=success"
    cancel_url = f"{base_redirect}/dashboard/billing?status=cancelled"

    payment_res = await grow_service.create_payment_page(
        amount=final_price,
        description=description,
        customer_name=user.name,
        customer_phone=user.assigned_phone_number or "0500000000",
        user_id=str(user.id),
        success_url=success_url,
        cancel_url=cancel_url,
    )

    if payment_res.get("status") == 1:
        return {
            "status": "pending_payment",
            "payment_required": True,
            "original_price": base_price,
            "final_price": final_price,
            "discount_percent": benefit["discount_percent"] if benefit else 0,
            "payment_url": payment_res.get("url"),
        }
    raise HTTPException(status_code=500, detail="Failed to initialize payment gateway.")


@router.post("/webhook/grow")
async def grow_payment_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives server-to-server confirmation from Meshulam and upgrades subscription upon payment.
    """
    try:
        data = await request.form()

        payment_status = data.get("status")
        user_id = data.get("custom_field_1")
        transaction_id = data.get("transaction_id")
        amount = data.get("sum")

        logger.info(f"Received Grow Webhook. Status: {payment_status}, User: {user_id}")

        if str(payment_status) == "1" and user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.plan_tier = PlanTier.PRO
                user.subscription_status = SubscriptionStatus.ACTIVE
                db.flush()

                new_log = AuditLog(
                    user_id=str(user.id),
                    action="SUBSCRIPTION_PAID",
                    details={
                        "transaction_id": transaction_id,
                        "amount": amount,
                        "provider": "Grow/Meshulam",
                    },
                )
                db.add(new_log)
                db.commit()

                logger.info(
                    f"💰 User {user.email} upgraded to PRO via Grow Webhook. TXN: {transaction_id}"
                )
                return {"status": "success", "message": "Subscription activated."}
            logger.error(f"Webhook matched unknown User ID: {user_id}")

        return {
            "status": "ignored",
            "message": "Not a successful transaction or missing user ID.",
        }

    except Exception as e:
        db.rollback()
        logger.error(f"🔥 Webhook Processing Error: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")


@router.post("/apply-coupon")
@router.post("/redeem-coupon")
async def redeem_coupon(
    payload: CouponRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Applies a coupon code:
    - 100% discount coupons immediately upgrade the tenant (lifting the FREE 1-lead limit).
    - Partial discount coupons (<100%) calculate the reduced price and return a discounted checkout quote.
    """
    code = payload.coupon_code.upper().strip()

    if code not in ACTIVE_COUPONS:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")

    benefit = ACTIVE_COUPONS[code]
    target_plan_name = benefit["plan"].upper()
    discount_pct = int(benefit.get("discount_percent", 100))
    base_price = PLAN_BASE_PRICES_ILS.get(target_plan_name, 199.00)
    final_price = round(max(0.0, base_price * (100 - discount_pct) / 100.0), 2)

    if discount_pct < 100:
        return {
            "status": "discount_applied",
            "activated": False,
            "coupon_code": code,
            "target_plan": target_plan_name,
            "discount_percent": discount_pct,
            "original_price": base_price,
            "final_price": final_price,
            "desc": benefit["desc"],
            "message": f"Coupon applied: {discount_pct}% discount ({final_price:.2f} ILS instead of {base_price:.2f} ILS).",
        }

    try:
        target_enum = PlanTier.PRO if target_plan_name == "PRO" else PlanTier.STARTER
        if user.plan_tier == target_enum and user.subscription_status == SubscriptionStatus.ACTIVE:
            return {
                "status": "success",
                "activated": True,
                "message": f"Plan is already {target_enum.value}",
                "plan": user.plan_tier.value,
                "original_price": base_price,
                "final_price": 0.0,
            }

        user.plan_tier = target_enum
        user.subscription_status = SubscriptionStatus.ACTIVE
        db.flush()

        new_log = AuditLog(
            user_id=str(user.id),
            action="COUPON_REDEEMED",
            details={
                "coupon_code": code,
                "discount_percent": discount_pct,
                "final_price": 0.0,
                "plan": target_enum.value,
            },
        )
        db.add(new_log)
        db.commit()
        db.refresh(user)

        logger.info(f"✅ COUPON SUCCESS: User {user.id} upgraded to {target_enum.value} (0 ILS).")

        return {
            "status": "success",
            "activated": True,
            "message": f"Coupon applied! Cost reduced to 0 ILS. You are now a {target_enum.value} member.",
            "plan": user.plan_tier.value,
            "discount_percent": discount_pct,
            "original_price": base_price,
            "final_price": 0.0,
            "desc": benefit["desc"],
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Database error during coupon redemption: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
