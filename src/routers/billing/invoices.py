# src/routers/billing/invoices.py
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Internal Project Imports
from src.security.dependencies import get_current_user
from src.database.session import get_db
from src.database.models import User, PlanTier

router = APIRouter(tags=["Billing - Invoices"])
logger = logging.getLogger("BillingInvoices")

# --- Schemas ---

class SubscriptionInfo(BaseModel):
    """Schema representing the user's active subscription state."""
    plan_tier: PlanTier
    is_active: bool
    # TODO: Add fields for next_billing_date, payment_method_last4, etc., once integrated.

class InvoiceResponse(BaseModel):
    """Schema representing a single historical invoice/receipt."""
    id: str
    transaction_id: str
    amount: float
    currency: str = "ILS"
    date: datetime
    download_url: str

# --- Routes ---

@router.get("/my-plan", response_model=SubscriptionInfo)
async def get_current_plan(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the current subscription status of the authenticated user.
    """
    return {
        "plan_tier": user.plan_tier,
        "is_active": user.is_active
    }


@router.get("/", response_model=List[InvoiceResponse])
async def list_user_invoices(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    TODO: Core B2B SaaS Requirement.
    Retrieves a history of all generated invoices/receipts for the user's accounting needs.
    Currently acts as a placeholder until a digital invoicing provider is integrated.
    """
    logger.info(f"User {user.email} requested invoice history.")
    
    # Returning an empty list safely handles frontend requests without breaking the UI.
    return []


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    TODO: Core B2B SaaS Requirement.
    Fetches the official PDF tax invoice/receipt for a specific transaction.
    """
    logger.warning(
        f"User {user.email} attempted to download invoice PDF: {invoice_id}. "
        "Feature not implemented yet."
    )
    
    # HTTP 501 Not Implemented is the REST standard for future endpoints
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="PDF Invoice generation is currently under development."
    )