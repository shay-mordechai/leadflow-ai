# src/routers/phones.py
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any
from pydantic import BaseModel

from src.config import settings
from src.routers.auth import get_current_user

# Professional English Comment:
# Initialize Router for Phone Management operations.
# This module handles searching and purchasing real DID numbers via providers (Twilio/Telnyx).
router = APIRouter()
logger = logging.getLogger("PhoneSystem")

class PhoneNumber(BaseModel):
    number: str
    country: str
    capabilities: List[str]
    price_monthly: float
    provider: str

@router.get("/available", response_model=List[PhoneNumber])
async def search_available_phones(
    country_code: str = Query("IL", min_length=2, max_length=2, description="ISO Country Code"),
    user: Dict = Depends(get_current_user)
):
    """
    Search for available phone numbers to purchase.
    Currently returns Mock Data for verification purposes.
    """
    logger.info(f"User {user['user_id']} is searching for phones in {country_code}")

    if not settings.ENABLE_REAL_PHONE_PURCHASE:
         raise HTTPException(status_code=403, detail="Phone purchase module is disabled.")

    # Mock Data for IL (Israel)
    if country_code.upper() == "IL":
        return [
            {
                "number": "+972541234567",
                "country": "IL",
                "capabilities": ["voice", "sms"],
                "price_monthly": 5.00,
                "provider": "LeadFlow Mock"
            },
            {
                "number": "+972509876543",
                "country": "IL",
                "capabilities": ["voice"],
                "price_monthly": 3.50,
                "provider": "LeadFlow Mock"
            }
        ]
    
    return []

@router.post("/purchase")
async def purchase_phone_number(
    phone_number: str,
    user: Dict = Depends(get_current_user)
):
    """
    Simulate a phone number purchase.
    """
    logger.info(f"User {user['user_id']} attempting to purchase {phone_number}")
    return {"status": "success", "message": f"Number {phone_number} purchased successfully (Simulation)."}