import logging
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

from src.database.session import get_db
from src.database.models import Lead, User, LeadSource, LeadStatus
from src.security.dependencies import get_current_user

# Professional English Comment: Initialize Router
router = APIRouter(tags=["Leads Management"])

# Professional English Comment: Configure local logger
logger = logging.getLogger(__name__)

# --- Schemas ---
class PagixLead(BaseModel):
    name: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=9)
    email: Optional[EmailStr] = None
    source: str = Field(default="pagix_landing_page")

class LeadResponse(BaseModel):
    id: str
    name: str
    phone_number: str
    status: str
    created_at: str
    
    class Config:
        from_attributes = True

# --- Routes ---

@router.get("/", response_model=List[LeadResponse])
def get_my_leads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # <--- THE SECURITY GATEKEEPER
):
    """
    SECURE ENDPOINT: Returns leads ONLY for the logged-in user.
    Hacker proofing: 
    1. 'get_current_user' validates the Token. If invalid -> 401 Error immediately.
    2. The query filters by 'current_user.id'. User A can NEVER see User B's leads.
    """
    leads = db.query(Lead).filter(Lead.user_id == current_user.id).all()
    return leads

@router.post("/pagix", status_code=status.HTTP_201_CREATED)
async def receive_pagix_lead(
    lead_data: PagixLead, 
    db: Session = Depends(get_db)
    # Note: Webhooks usually don't have user tokens. 
    # In the future, we will add an API Key check here to identify the target user.
    # For now, we will attach it to the first admin user found for testing.
):
    """
    Webhook Endpoint: Receives lead data and saves to DB.
    """
    try:
        # TEMP: Find a default user to assign the lead to (since webhook has no login context)
        # In production, the URL would be /pagix/{user_id} or contain an API Key.
        default_user = db.query(User).first()
        if not default_user:
             raise HTTPException(status_code=500, detail="No users in system to assign lead")

        # Create DB Entry
        new_lead = Lead(
            user_id=default_user.id,
            # Using the setters we defined in models.py (which handle encryption!)
            name=lead_data.name,
            phone_number=lead_data.phone,
            source=LeadSource.LANDING_PAGE,
            status=LeadStatus.NEW
        )
        
        db.add(new_lead)
        db.commit()
        
        logger.info(f"New Lead Saved: {lead_data.name} for User: {default_user.email}")

        return {"status": "success", "lead_id": str(new_lead.id)}

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )