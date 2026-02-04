# src/routers/phones.py
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

# Ensure these modules exist in your project structure
from src.routers.auth import get_current_user
from src.services.phone_service import phone_service 

router = APIRouter()
logger = logging.getLogger("PhoneSystem")

# --- Security & Validation Models ---

class PhoneNumber(BaseModel):
    number: str
    country: str
    capabilities: List[str]
    price_monthly: float
    provider: str

class PurchaseRequest(BaseModel):
    # Field validation prevents empty strings or super long inputs (SAST protection)
    phone_number: str = Field(..., min_length=10, max_length=20, description="E.164 formatted phone number")
    friendly_name: str = Field("My Studio Line", max_length=50)

# --- Routes ---

@router.get("/available", response_model=List[PhoneNumber])
async def search_available_phones(
    country_code: str = Query("US", min_length=2, max_length=2, pattern="^[A-Z]{2}$"), # Regex validation
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
        logger.error(f"Search failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Provider search failed")

@router.post("/purchase")
async def purchase_phone_number(
    request: PurchaseRequest,
    user: Dict = Depends(get_current_user)
):
    """
    Buys a number and immediately configures the AI Webhooks.
    SECURED: Only allows 'premium' users to purchase.
    """
    user_id = user.get('user_id', 'unknown')
    user_plan = user.get('plan_type', 'free') # Default to free if missing

    # --- SECURITY GATE: BUSINESS LOGIC CHECK ---
    if user_plan != "premium":
        logger.warning(f"⛔ Blocked purchase attempt by FREE user: {user_id}")
        raise HTTPException(
            status_code=403, 
            detail="Purchase restricted to Premium subscribers. Please upgrade your plan."
        )
    # -------------------------------------------

    logger.info(f"User {user_id} (Plan: {user_plan}) initiating purchase for {request.phone_number}")
    
    result = await phone_service.purchase_number(
        phone_number=request.phone_number, 
        user_id=str(user_id),
        friendly_name=request.friendly_name
    )
    
    if result.get("status") == "failed":
        logger.error(f"Purchase failed for user {user_id}: {result.get('detail')}")
        raise HTTPException(status_code=500, detail=result.get("detail", "Purchase failed"))
        
    return result