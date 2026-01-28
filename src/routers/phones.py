# src/routers/phones.py
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict
from pydantic import BaseModel

from src.routers.auth import get_current_user
from src.services.phone_service import phone_service # <--- Import the Service

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
    country_code: str = Query("IL", min_length=2, max_length=2),
    user: Dict = Depends(get_current_user)
):
    """
    Returns REAL available numbers from providers (with our markup).
    """
    logger.info(f"User {user['user_id']} searching for numbers in {country_code}")
    
    # Delegate to the Service Manager
    results = await phone_service.search_best_numbers(country_code)
    
    return results

@router.post("/purchase")
async def purchase_phone_number(
    phone_number: str,
    user: Dict = Depends(get_current_user)
):
    logger.info(f"User {user['user_id']} initiating purchase for {phone_number}")
    
    result = await phone_service.purchase_number(phone_number, user['user_id'])
    
    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result.get("detail", "Purchase failed"))
        
    return result