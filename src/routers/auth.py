import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.database.session import get_db
from src.database.models import Tenant
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# Schema to match your JavaScript fetch payload
class RegisterSchema(BaseModel):
    name: str
    personal_whatsapp: str
    business_whatsapp: Optional[str] = None
    needs_new_number: bool
    business_type: str
    city_coverage: str

@router.post("/register")
async def register_tenant(data: RegisterSchema, db: Session = Depends(get_db)):
    # 1. Check if the personal phone already exists in the system
    existing = db.query(Tenant).filter(Tenant.personal_whatsapp == data.personal_whatsapp).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="מספר וואטסאפ אישי זה כבר קיים במערכת"
        )

    # 2. Generate a secure API Key for the new tenant
    # Since your model requires api_key_hash, we generate a random one for now
    generated_api_key = secrets.token_urlsafe(32)

    # 3. Create new Tenant instance mapping to your Model
    new_tenant = Tenant(
        name=data.name,
        whatsapp_number=data.business_whatsapp if not data.needs_new_number else None,
        personal_whatsapp=data.personal_whatsapp,
        requires_new_number=data.needs_new_number,
        city_coverage=data.city_coverage,
        business_type=data.business_type,
        api_key_hash=generated_api_key, # In production, hash this key!
        is_active=True
    )

    try:
        db.add(new_tenant)
        db.commit()
        db.refresh(new_tenant)

        return {
            "status": "success",
            "tenant_id": str(new_tenant.id),
            "upsell_triggered": data.needs_new_number
        }
    except Exception as e:
        db.rollback()
        # Professional Logging
        print(f"Database Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="שגיאה פנימית ביצירת החשבון"
        )
