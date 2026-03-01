# src/routers/phones.py
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import User, PhoneNumber, PlanTier
from src.security.dependencies import get_current_user
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
    provider: str = "twilio" 

# --- Endpoints ---

@router.get("/available", response_model=List[PhoneResult])
async def search_available_phones(
    country_code: str = Query("IL", min_length=2, max_length=2),
    area_code: Optional[str] = Query(None, description="Preferred prefix e.g., '03', '04', 'mobile'"),
    current_user: User = Depends(get_current_user)
):
    """
    Searches for available numbers across ALL providers.
    Filters by area_code (prefix) to match user's business region.
    """
    try:
        # Call the unified service that aggregates results from Twilio/Vonage/SignalWire
        results = await phone_service.search_best_numbers(country_code)
        
        # --- SMART ROUTING: Filter by Area Code ---
        if area_code and results:
            filtered_results = []
            
            for phone in results:
                num_str = phone.get("number", "")
                
                if area_code == "mobile":
                    # Israel mobile/national prefixes usually +9725 or +9727
                    if "+9725" in num_str or "+9727" in num_str:
                        filtered_results.append(phone)
                else:
                    # Match specific area codes like +9723 (Tel Aviv)
                    # We strip the leading 0 from the requested area code (e.g., "03" -> "3")
                    clean_prefix = area_code.lstrip('0')
                    if f"+972{clean_prefix}" in num_str:
                        filtered_results.append(phone)
            
            # If we found exact matches for the region, return them
            if filtered_results:
                return filtered_results
                
            # Fallback: If no exact matches for the specific region, 
            # we return mobile/national numbers as an alternative instead of failing completely.
            logger.info(f"No exact matches for region {area_code}, falling back to national numbers.")
            fallback_results = [p for p in results if "+9725" in p.get("number", "") or "+9727" in p.get("number", "")]
            return fallback_results if fallback_results else results

        # If no area code was requested, return all
        return results
        
    except Exception as e:
        logger.error(f"Global search failed: {e}")
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
            provider_id=result.get("sid", "unknown"),
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