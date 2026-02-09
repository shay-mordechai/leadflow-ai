# src/routers/billing/invoices.py
import logging
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Internal Project Imports
from src.security.dependencies import get_current_user
from src.database.session import get_db
from src.database.models import User, PlanTier

router = APIRouter(tags=["Billing - Invoices"])
logger = logging.getLogger("BillingInvoices")

# --- Models ---
class SubscriptionInfo(BaseModel):
    plan_tier: PlanTier
    is_active: bool
    # In the future: next_billing_date, payment_history, etc.

# --- Routes ---

@router.get("/my-plan", response_model=SubscriptionInfo)
async def get_current_plan(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the current subscription status of the user.
    Future: This will also list PDF invoices.
    """
    return {
        "plan_tier": user.plan_tier,
        "is_active": user.is_active
    }