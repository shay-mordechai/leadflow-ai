# src/routers/phones.py
import logging
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel

# Ensure these modules exist in your project structure
from src.routers.auth import get_current_user
from src.services.phone_service import phone_service 

router = APIRouter()
logger = logging.getLogger("PhoneSystem")

# Pydantic Model for Response
class PhoneNumber(BaseModel):
    number: str
    country: str
    capabilities: List[str]
    price_monthly: float
    provider: str

# Pydantic Model for Purchase Request
class PurchaseRequest(BaseModel):
    phone_number: str
    friendly_name: str = "My Studio Line"

@router.get("/available", response_model=List[PhoneNumber])
async def search_available_phones(
    country_code: str = Query("US", min_length=2, max_length=2),
    area_code: str = Query(None, min_length=3, max_length=3),
    user: Dict = Depends(get_current_user)
):
    """
    Returns REAL available numbers from SignalWire (with our markup).
    Defaults to US for testing (SignalWire trial usually limits IL numbers).
    """
    user_id = user.get('user_id', 'unknown')
    logger.info(f"User {user_id} searching for numbers in {country_code}")
    
    try:
        # Delegate to the Service Manager
        results = await phone_service.search_best_numbers(country_code, area_code)
        return results
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Provider search failed")

@router.post("/purchase")
async def purchase_phone_number(
    request: PurchaseRequest,
    user: Dict = Depends(get_current_user)
):
    """
    Buys a number and immediately configures the AI Webhooks.
    """
    user_id = user.get('user_id', 'unknown')
    logger.info(f"User {user_id} initiating purchase for {request.phone_number}")
    
    result = await phone_service.purchase_number(
        phone_number=request.phone_number, 
        user_id=user_id,
        friendly_name=request.friendly_name
    )
    
    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result.get("detail", "Purchase failed"))
        
    return result