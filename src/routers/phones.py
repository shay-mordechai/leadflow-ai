# src/routers/phones.py
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import User, PhoneNumber, PlanTier
from src.security.dependencies import get_current_user
# CORRECT IMPORT PATH
from src.services.providers.twilio import twilio_provider

router = APIRouter()
logger = logging.getLogger("PhoneSystem")

class PhoneResult(BaseModel):
    number: str
    country: str = "IL"
    price_monthly: float = 1.00
    provider: str

class PurchaseRequest(BaseModel):
    phone_number: str
    country_code: str = "IL"

@router.get("/available", response_model=List[PhoneResult])
async def search_available_phones(
    country_code: str = Query("IL", min_length=2, max_length=2),
    user: User = Depends(get_current_user)
):
    results = []
    try:
        t_res = twilio_provider.search_numbers(country_code=country_code)
        for item in t_res:
            results.append(PhoneResult(
                number=item.get("number"),
                country=country_code,
                price_monthly=item.get("price_monthly", 1.15),
                provider="twilio"
            ))
    except Exception as e:
        logger.error(f"Search failed: {e}")
    return results

@router.post("/purchase")
async def purchase_phone_number(
    request: PurchaseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # 1. SECURITY: Only PRO users can buy
    if user.plan_tier != PlanTier.PRO:
        raise HTTPException(status_code=403, detail="Phone purchasing is restricted to PRO plan members.")

    # 2. Check Existing
    if db.query(PhoneNumber).filter(PhoneNumber.owner_id == user.id).first():
        raise HTTPException(status_code=400, detail="User already has a phone number.")

    try:
        provider_id = twilio_provider.buy_number(request.phone_number)
        new_phone = PhoneNumber(
            number=request.phone_number,
            provider="twilio",
            provider_id=provider_id,
            owner_id=user.id,
            is_active=True,
            country_code=request.country_code
        )
        db.add(new_phone)
        db.commit()
        return {"status": "success", "phone_number": new_phone.number}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))