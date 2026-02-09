# src/routers/phones.py
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import User, PhoneNumber, PlanTier
from src.security.dependencies import get_current_user
# FIXED IMPORT: Use the unified service, not just Twilio
from src.services.phone import phone_service

router = APIRouter()
logger = logging.getLogger("PhoneRouter")

# --- Response Models ---
class PhoneResult(BaseModel):
    number: str
    country: str = "IL"
    price_monthly: float
    provider: str
    capabilities: List[str] = []

class PurchaseRequest(BaseModel):
    phone_number: str
    country_code: str = "IL"
    # Added optional provider field to know where to buy from (default to twilio if missing)
    provider: str = "twilio" 

# --- Endpoints ---

@router.get("/available", response_model=List[PhoneResult])
async def search_available_phones(
    country_code: str = Query("IL", min_length=2, max_length=2),
    current_user: User = Depends(get_current_user)
):
    """
    Searches for available numbers across ALL providers (Twilio, Vonage, SignalWire).
    """
    try:
        # Call the unified service that aggregates results
        results = await phone_service.search_best_numbers(country_code)
        return results
    except Exception as e:
        logger.error(f"Global search failed: {e}")
        # Return empty list instead of 500 to avoid breaking frontend
        return []

@router.post("/purchase")
async def purchase_phone_number(
    request: PurchaseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Purchases a number from the specified provider.
    """
    # 1. SECURITY: Only PRO users can buy
    if user.plan_tier != PlanTier.PRO:
        raise HTTPException(status_code=403, detail="Phone purchasing is restricted to PRO plan members.")

    # 2. Check Existing (One number per user rule)
    if db.query(PhoneNumber).filter(PhoneNumber.owner_id == user.id).first():
        raise HTTPException(status_code=400, detail="User already has a phone number.")

    try:
        # 3. Execute Purchase via Unified Service
        # We pass the provider explicitly (twilio/vonage/signalwire)
        result = await phone_service.purchase_number(
            provider=request.provider,
            phone_number=request.phone_number,
            user_id=str(user.id)
        )

        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=result.get("detail", "Purchase failed"))

        # 4. Save to Database
        new_phone = PhoneNumber(
            number=request.phone_number,
            provider=request.provider,
            provider_id=result.get("sid", "unknown"), # Vonage doesn't always return SID
            owner_id=user.id,
            is_active=True,
            country_code=request.country_code
        )
        db.add(new_phone)
        db.commit()
        
        logger.info(f"✅ Database updated for user {user.id}")
        return {"status": "success", "phone_number": new_phone.number, "provider": request.provider}

    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Purchase Transaction Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))