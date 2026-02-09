# src/routers/settings.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from src.database.session import get_db
from src.database.models import BusinessProfile, User
from src.security.dependencies import get_current_user

router = APIRouter(prefix="/settings", tags=["AI Configuration"])

class AISettingsSchema(BaseModel):
    business_name: str
    business_type: str
    ai_tone: str
    products_services: Optional[str] = None
    custom_instructions: Optional[str] = None

@router.get("/", response_model=AISettingsSchema)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch current AI settings"""
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    if not profile:
        # Return empty default if not set yet
        return AISettingsSchema(
            business_name=current_user.name,
            business_type="General",
            ai_tone="Professional",
            products_services="",
            custom_instructions=""
        )
    return profile

@router.post("/", status_code=status.HTTP_200_OK)
def update_settings(
    data: AISettingsSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update AI Brain configuration"""
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    
    if not profile:
        # Create new profile
        profile = BusinessProfile(
            id=current_user.id, # 1-to-1 relationship logic
            user_id=current_user.id,
            business_name=data.business_name,
            business_type=data.business_type,
            ai_tone=data.ai_tone,
            products_services=data.products_services,
            custom_instructions=data.custom_instructions
        )
        db.add(profile)
    else:
        # Update existing
        profile.business_name = data.business_name
        profile.business_type = data.business_type
        profile.ai_tone = data.ai_tone
        profile.products_services = data.products_services
        profile.custom_instructions = data.custom_instructions
    
    db.commit()
    return {"status": "success", "message": "AI Brain updated successfully"}