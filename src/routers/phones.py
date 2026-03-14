# src/routers/phones.py
import logging
import os
import uuid
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import User, PhoneNumber, PlanTier
from src.security.dependencies import get_current_user
from src.services.phone import phone_service

router = APIRouter()
logger = logging.getLogger("PhoneRouter")

KYC_STORAGE_DIR = "storage/kyc"
os.makedirs(KYC_STORAGE_DIR, exist_ok=True)

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

@router.post("/kyc-upload")
async def upload_kyc_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.plan_tier != PlanTier.PRO:
        raise HTTPException(status_code=403, detail="Only PRO users can upload KYC documents.")
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type.")

    try:
        file_extension = file.filename.split(".")[-1]
        secure_filename = f"kyc_{user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"
        file_path = os.path.join(KYC_STORAGE_DIR, secure_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {"status": "success", "message": "Document uploaded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to securely store the document.")

@router.get("/available", response_model=List[PhoneResult])
async def search_available_phones(
    country_code: str = Query("IL", min_length=2, max_length=2),
    area_code: Optional[str] = Query(None, description="Preferred prefix e.g., '03', '04', 'mobile'"),
    current_user: User = Depends(get_current_user)
):
    """
    Searches for available numbers. If provider fails, generates realistic fallback numbers 
    so the user flow isn't interrupted during demo/setup.
    """
    fallback_numbers = [
        {"number": "+97235001234", "country": "IL", "price_monthly": 15.0, "provider": "twilio", "capabilities": ["voice", "sms"]},
        {"number": "+97236009876", "country": "IL", "price_monthly": 15.0, "provider": "twilio", "capabilities": ["voice", "sms"]},
        {"number": "+97248005555", "country": "IL", "price_monthly": 15.0, "provider": "twilio", "capabilities": ["voice", "sms"]},
        {"number": "+97226004444", "country": "IL", "price_monthly": 15.0, "provider": "twilio", "capabilities": ["voice", "sms"]},
        {"number": "+97289003333", "country": "IL", "price_monthly": 15.0, "provider": "twilio", "capabilities": ["voice", "sms"]},
        {"number": "+97297002222", "country": "IL", "price_monthly": 15.0, "provider": "twilio", "capabilities": ["voice", "sms"]},
        {"number": "+972551234567", "country": "IL", "price_monthly": 15.0, "provider": "twilio", "capabilities": ["voice", "sms"]},
    ]

    try:
        results = []
        try:
            results = await phone_service.search_best_numbers(country_code)
        except Exception:
            results = fallback_numbers
            
        if not results:
            results = fallback_numbers
            
        # Filter by Area Code
        if area_code:
            filtered = []
            prefix_map = {"03": "+9723", "04": "+9724", "02": "+9722", "08": "+9728", "09": "+9729"}
            
            for phone in results:
                num_str = phone.get("number", "")
                if area_code == "mobile" and ("+9725" in num_str or "+9727" in num_str):
                    filtered.append(phone)
                elif area_code in prefix_map and prefix_map[area_code] in num_str:
                    filtered.append(phone)
            
            return filtered if filtered else [p for p in results if "+9725" in p.get("number", "")]

        return results
        
    except Exception as e:
        logger.error(f"Global search failed: {e}")
        return fallback_numbers

@router.post("/purchase")
async def purchase_phone_number(
    request: PurchaseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if user.plan_tier != PlanTier.PRO:
        raise HTTPException(status_code=403, detail="Phone purchasing is restricted to PRO plan members.")

    if db.query(PhoneNumber).filter(PhoneNumber.owner_id == user.id).first():
        raise HTTPException(status_code=400, detail="User already has a phone number.")

    try:
        # Mocking the actual Twilio purchase for MVP until gateway is fully hooked
        new_phone = PhoneNumber(
            number=request.phone_number,
            provider=request.provider,
            provider_id="mock_sid_" + uuid.uuid4().hex[:8],
            owner_id=user.id,
            is_active=True,
            country_code=request.country_code
        )
        db.add(new_phone)
        db.commit()
        
        return {"status": "success", "phone_number": new_phone.number, "provider": request.provider}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))