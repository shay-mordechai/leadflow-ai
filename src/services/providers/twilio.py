# src/services/providers/twilio.py
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.security.dependencies import get_current_user
from src.database.models import User, PhoneNumber
# Import the provider directly
from src.services.providers.twilio import twilio_provider 

router = APIRouter()
logger = logging.getLogger("PhoneSystem")

# --- Validation Models ---

class PhoneResult(BaseModel):
    number: str
    friendly_name: Optional[str] = None
    locality: Optional[str] = None
    country: str = "IL"
    price_monthly: float = 1.00
    capabilities: List[str] = []
    provider: str = "twilio"

class PurchaseRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=20, description="E.164 format")
    country_code: str = "IL"

# --- Routes ---

@router.get("/available", response_model=List[PhoneResult])
async def search_available_phones(
    country_code: str = Query("IL", min_length=2, max_length=2),
    contains: Optional[str] = Query(None, min_length=2, max_length=10),
    user: User = Depends(get_current_user)
):
    """
    Returns available numbers from Twilio.
    """
    logger.info(f"User {user.id} searching for numbers in {country_code}")
    
    try:
        results = twilio_provider.search_numbers(
            country_code=country_code, 
            contains=contains
        )
        return results

    except Exception as e:
        logger.error(f"Search failed: {e}")
        # Return empty list to prevent frontend crash
        return []

@router.post("/purchase")
async def purchase_phone_number(
    request: PurchaseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Buys a number via Twilio and assigns it to the User in the DB.
    """
    # 1. Check if user already has a number
    existing_phone = db.query(PhoneNumber).filter(PhoneNumber.owner_id == user.id).first()
    if existing_phone:
        raise HTTPException(status_code=400, detail="You already have an active phone number.")

    logger.info(f"User {user.id} purchasing {request.phone_number}")
    
    try:
        # 2. Execute Purchase on Twilio
        provider_id = twilio_provider.buy_number(
            phone_number=request.phone_number,
            friendly_name=f"LeadFlow_{user.business_name or user.name}"
        )
        
        if not provider_id:
            raise HTTPException(status_code=500, detail="Failed to purchase number from provider.")

        # 3. Save to Database
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
        db.refresh(new_phone)
        
        return {"status": "success", "phone_number": new_phone.number}
        
    except Exception as e:
        logger.error(f"Purchase exception: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))