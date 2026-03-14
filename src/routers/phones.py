# src/routers/phones.py
import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import User, PhoneNumber, PlanTier
from src.security.dependencies import get_current_user
from src.services.phone import phone_service
from src.services.providers.twilio import twilio_provider
from src.services.storage.s3_service import s3_service

router = APIRouter(prefix="/api/v1/phones", tags=["Phones"])
logger = logging.getLogger("PhoneRouter")

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
    """
    Handles KYC document upload to Amazon S3 (Secure Storage).
    No local files are saved.
    """
    if user.plan_tier != PlanTier.PRO.value and user.plan_tier != PlanTier.PRO:
        raise HTTPException(status_code=403, detail="Only PRO users can upload KYC documents.")
    
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPG, PNG, and PDF are allowed.")

    try:
        # 1. Generate a secure, unique S3 key (path)
        file_extension = file.filename.split(".")[-1]
        s3_key = f"kyc/{user.id}/{uuid.uuid4().hex[:12]}.{file_extension}"

        # 2. Upload directly to S3
        success = s3_service.upload_fileobj(
            file_obj=file.file,
            object_name=s3_key,
            content_type=file.content_type
        )

        if not success:
            raise HTTPException(status_code=500, detail="S3 upload failed")

        logger.info(f"📢 KYC Document uploaded to S3 by {user.email}. Key: {s3_key}")
        
        return {
            "status": "success", 
            "message": "המסמך הועלה לענן המאובטח וממתין לאישור.",
            "file_id": s3_key
        }
    except Exception as e:
        logger.error(f"KYC S3 upload failed for {user.email}: {e}")
        raise HTTPException(status_code=500, detail="נכשלנו לשמור את המסמך בענן המאובטח.")

@router.get("/available", response_model=List[PhoneResult])
async def search_available_phones(
    country_code: str = Query("IL", min_length=2, max_length=2),
    area_code: Optional[str] = Query(None, description="Preferred prefix e.g., '03', '04', 'mobile'"),
    current_user: User = Depends(get_current_user)
):
    """
    Searches for REAL available numbers via Twilio/Providers.
    No mock fallbacks.
    """
    try:
        results = await phone_service.search_best_numbers(country_code)
            
        if not results:
            raise HTTPException(status_code=404, detail="לא נמצאו מספרים פנויים באזור זה דרך ספקי התקשורת.")
            
        if area_code:
            filtered = []
            prefix_map = {"03": "+9723", "04": "+9724", "02": "+9722", "08": "+9728", "09": "+9729"}
            for phone in results:
                num_str = phone.get("number", "")
                if area_code == "mobile" and ("+9725" in num_str or "+9727" in num_str):
                    filtered.append(phone)
                elif area_code in prefix_map and prefix_map[area_code] in num_str:
                    filtered.append(phone)
            
            final_results = filtered if filtered else [p for p in results if "+9725" in p.get("number", "")]
            if not final_results:
                raise HTTPException(status_code=404, detail=f"לא נמצאו מספרים עבור הקידומת {area_code}.")
            return final_results

        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Global telecom search failed: {e}")
        raise HTTPException(status_code=500, detail="שגיאת תקשורת מול שרת הטלפוניה (Twilio).")

@router.post("/purchase")
async def purchase_phone_number(
    request: PurchaseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Executes a LIVE purchase of the phone number against Twilio API
    and allocates it to the user in the database.
    """
    if user.plan_tier != PlanTier.PRO.value and user.plan_tier != PlanTier.PRO:
        raise HTTPException(status_code=403, detail="Phone purchasing is restricted to PRO plan members.")

    if db.query(PhoneNumber).filter(PhoneNumber.owner_id == user.id).first():
        raise HTTPException(status_code=400, detail="User already has a phone number.")

    try:
        # LIVE PURCHASE CALL TO TWILIO (No Mocks!)
        purchased_sid = twilio_provider.buy_number(
            phone_number=request.phone_number,
            friendly_name=f"LeadFlow - {user.business_name or user.name}"
        )
        
        if not purchased_sid:
            raise Exception("Twilio API returned None for purchased SID.")

        # Save to DB only if Twilio purchase was successful
        new_phone = PhoneNumber(
            number=request.phone_number,
            provider=request.provider,
            provider_id=purchased_sid,
            owner_id=user.id,
            is_active=True,
            country_code=request.country_code
        )
        db.add(new_phone)
        db.commit()
        
        logger.info(f"✅ Real Number purchased: {new_phone.number} for user {user.email}")
        
        return {
            "status": "success", 
            "phone_number": new_phone.number, 
            "provider": request.provider
        }
    except Exception as e:
        db.rollback()
        logger.error(f"REAL Twilio purchase failed for {user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="רכישת המספר ב-Twilio נכשלה. האם יש יתרה בחשבון?")