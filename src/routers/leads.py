from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import List
from src.database.session import get_db
from src.database.models import Lead
from src.security.tenant import get_current_tenant_id
from src.security.validation import SecurityValidator

router = APIRouter(tags=["Leads"])

# Pydantic DTO (Data Transfer Object) for stricter validation
class CreateLeadSchema(BaseModel):
    name: str
    phone: str

    @field_validator('name')
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        clean = SecurityValidator.sanitize_input(v)
        if len(clean) < 2:
            raise ValueError("Name too short")
        return clean

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        is_valid, clean_num = SecurityValidator.validate_israeli_phone(v)
        if not is_valid:
            raise ValueError("Invalid Israeli phone number")
        return clean_num

@router.get("/")
def list_leads(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Returns leads strictly for the authenticated tenant.
    Encryption is handled automatically by the Model TypeDecorator.
    """
    return Lead.get_query(db).all()

@router.post("/")
def create_lead(
    lead_data: CreateLeadSchema,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    # Check for duplicate within tenant
    existing = Lead.get_query(db).filter(Lead.phone_number == lead_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Lead already exists")

    new_lead = Lead(
        name=lead_data.name,
        phone_number=lead_data.phone,
        tenant_id=tenant_id
    )
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)

    return {"id": new_lead.id, "status": "created"}
