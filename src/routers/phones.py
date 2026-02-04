# src/routers/phones.py
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

# Ensure these modules exist in your project structure
from src.security.dependencies import get_current_user
from src.database.models import User
from src.services.phone_service import phone_service 

router = APIRouter()
logger = logging.getLogger("PhoneSystem")

# --- Security & Validation Models ---

class PhoneNumber(BaseModel):
    number: str
    country: str = "US"
    # Professional English Comment:
    # Added default values to prevent API validation errors if the provider 
    # (or Mock service) returns incomplete data.
    capabilities: List[str] = Field(default_factory=lambda: ["voice", "sms", "mms"])
    price_monthly: float = 1.00
    provider: str = "signalwire"

class PurchaseRequest(BaseModel):
    # Field validation prevents empty strings or super long inputs (SAST protection)
    phone_number: str = Field(..., min_length=10, max_length=20, description="E.164 formatted phone number")
    friendly_name: str = Field("My Studio Line", max_length=50)

# --- Routes ---

@router.get("/available", response_model=List[PhoneNumber])
async def search_available_phones(
    country_code: str = Query("US", min_length=2, max_length=2, pattern="^[A-Z]{2}$"), # Regex validation
    area_code: Optional[str] = Query(None, min_length=3, max_length=3),
    user: User = Depends(get_current_user)
):
    """
    Returns REAL available numbers from SignalWire/Twilio (with markup).
    Defaults to US for testing.
    """
    logger.info(f"User {user.id} searching for numbers in {country_code}")
    
    try:
        # Delegate to the Service Manager
        raw_results = await phone_service.search_best_numbers(country_code, area_code)
        
        # Professional English Comment:
        # Normalize data to ensure it strictly matches the Pydantic schema.
        # This prevents 500 errors if the provider omits optional fields.
        normalized_results = []
        for item in raw_results:
            # Handle case where item might be a dict or an object
            data = item.dict() if hasattr(item, 'dict') else item
            
            normalized_results.append(PhoneNumber(
                number=data.get("number"),
                country=data.get("country", country_code),
                capabilities=data.get("capabilities", ["voice", "sms"]),
                price_monthly=float(data.get("price_monthly", 1.00)),
                provider=data.get("provider", "signalwire")
            ))
            
        return normalized_results

    except Exception as e:
        logger.error(f"Search failed for user {user.id}: {e}")
        # Return empty list instead of crashing to allow UI to handle gracefully
        return []

@router.post("/purchase")
async def purchase_phone_number(
    request: PurchaseRequest,
    user: User = Depends(get_current_user)
):
    """
    Buys a number and immediately configures the AI Webhooks.
    SECURED: Only allows 'premium' or 'PRO' users to purchase.
    """
    # Professional English Comment:
    # Access User attributes safely (assuming SQLAlchemy model).
    # We allow 'premium' or 'PRO' (case-insensitive) to be safe.
    plan = str(user.plan_tier).lower() if hasattr(user, "plan_tier") else "free"

    # --- SECURITY GATE: BUSINESS LOGIC CHECK ---
    if plan not in ["premium", "pro"]:
        logger.warning(f"⛔ Blocked purchase attempt by FREE user: {user.id}")
        raise HTTPException(
            status_code=403, 
            detail="Purchase restricted to Premium subscribers. Please upgrade your plan."
        )
    # -------------------------------------------

    logger.info(f"User {user.id} (Plan: {plan}) initiating purchase for {request.phone_number}")
    
    try:
        result = await phone_service.purchase_number(
            phone_number=request.phone_number, 
            user_id=str(user.id),
            friendly_name=request.friendly_name
        )
        
        if result.get("status") == "failed":
            logger.error(f"Purchase failed for user {user.id}: {result.get('detail')}")
            raise HTTPException(status_code=500, detail=result.get("detail", "Purchase failed"))
            
        return result
        
    except Exception as e:
        logger.error(f"Purchase exception: {e}")
        raise HTTPException(status_code=500, detail="Internal Purchase Error")