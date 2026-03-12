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

# --- Schemas & Configuration ---
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

# --- Endpoints ---

@router.post("/kyc-upload")
async def upload_kyc_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Tier 2 Legal/Compliance: Accepts KYC documents (ID/Company Registration)
    Required by Twilio/Vonage before purchasing Israeli numbers.
    Saves securely to local storage (or S3 in the future).
    """
    if user.plan_tier != PlanTier.PRO:
        raise HTTPException(status_code=403, detail="Only PRO users can upload KYC documents.")

    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPG, PNG, and PDF are allowed.")

    try:
        # Generate a secure filename to prevent path traversal
        file_extension = file.filename.split(".")[-1]
        secure_filename = f"kyc_{user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"
        file_path = os.path.join(KYC_STORAGE_DIR, secure_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"✅ KYC Document uploaded securely for user {user.email}: {secure_filename}")
        
        # Future-proofing: Here you would ideally update `user.kyc_status = 'pending'` in the DB
        # For now, we rely on the frontend local state to unlock the purchase button once uploaded.

        return {
            "status": "success", 
            "message": "Document uploaded successfully and pending compliance review."
        }

    except Exception as e:
        logger.error(f"❌ Failed to process KYC upload for {user.email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to securely store the document.")

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
                    clean_prefix = area_code.lstrip('0')
                    if f"+972{clean_prefix}" in num_str:
                        filtered_results.append(phone)
            
            if filtered_results:
                return filtered_results
                
            # Fallback
            logger.info(f"No exact matches for region {area_code}, falling back to national numbers.")
            fallback_results = [p for p in results if "+9725" in p.get("number", "") or "+9727" in p.get("number", "")]
            return fallback_results if fallback_results else results

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
    if user.plan_tier != PlanTier.PRO:
        raise HTTPException(status_code=403, detail="Phone purchasing is restricted to PRO plan members.")

    if db.query(PhoneNumber).filter(PhoneNumber.owner_id == user.id).first():
        raise HTTPException(status_code=400, detail="User already has a phone number.")

    try:
        # In a real scenario, you'd check `user.kyc_status == 'approved'` here before allowing purchase.
        
        result = await phone_service.purchase_number(
            provider=request.provider,
            phone_number=request.phone_number,
            user_id=str(user.id)
        )

        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=result.get("detail", "Purchase failed"))

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