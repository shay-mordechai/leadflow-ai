# src/routers/leads.py
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Query
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
    """
    Schema for incoming webhook data from Landing Pages (Pagix/Elementor/Wix).
    """
    name: str = Field(..., min_length=2, description="Lead's full name")
    phone: str = Field(..., min_length=9, description="Lead's phone number")
    email: Optional[EmailStr] = None
    source: str = Field(default="pagix_landing_page")

class LeadResponse(BaseModel):
    """
    Schema for outgoing lead data to the Dashboard.
    """
    id: str
    name: str
    phone_number: str
    email: Optional[str] = None  # FIX: Added email to response
    status: str
    summary_text: Optional[str] = None # Useful for the dashboard
    suggested_reply: Optional[str] = None
    created_at: datetime # FIX: Changed from str to datetime for better sorting in frontend
    
    class Config:
        from_attributes = True

# --- Routes ---

@router.get("/", response_model=List[LeadResponse])
def get_my_leads(
    limit: int = Query(50, ge=1, le=100), # FIX: Added Pagination (Default 50, Max 100)
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    SECURE ENDPOINT: Returns leads ONLY for the logged-in user.
    Includes pagination to prevent server overload.
    """
    # Professional English Comment: 
    # Always filter by current_user.id to prevent horizontal privilege escalation.
    query = db.query(Lead).filter(Lead.user_id == current_user.id)
    
    # Apply sorting (newest first) and pagination
    leads = query.order_by(Lead.created_at.desc()).offset(offset).limit(limit).all()
    
    return leads

@router.post("/webhook/{user_id}", status_code=status.HTTP_201_CREATED)
async def receive_external_lead(
    user_id: str, # FIX: Accept user_id in URL to know who owns the lead
    lead_data: PagixLead, 
    db: Session = Depends(get_db)
):
    """
    Webhook Endpoint: Receives lead data from landing pages.
    The URL must contain the target User ID: /api/v1/leads/webhook/<USER_UUID>
    """
    try:
        # 1. Validate User Exists
        # We assume the 'user_id' acts as a public API key for the landing page configuration.
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
             logger.warning(f"Webhook failed: User ID {user_id} not found.")
             raise HTTPException(status_code=404, detail="Target user not found")

        # 2. Duplicate Check (Logic Upgrade)
        # Prevent spamming the same lead multiple times in a short period (optional but recommended)
        # Here we check if this phone number exists for this user in the 'NEW' status.
        existing_lead = db.query(Lead).filter(
            Lead.user_id == target_user.id,
            Lead.phone_number == lead_data.phone,
            Lead.status == LeadStatus.NEW
        ).first()

        if existing_lead:
            logger.info(f"Skipping duplicate lead {lead_data.phone} for user {user_id}")
            return {"status": "ignored", "message": "Lead already exists"}

        # 3. Create DB Entry
        new_lead = Lead(
            user_id=target_user.id,
            name=lead_data.name,
            phone_number=lead_data.phone,
            email=lead_data.email, # FIX: Now actually saving the email!
            source=LeadSource.LANDING_PAGE,
            status=LeadStatus.NEW
        )
        
        db.add(new_lead)
        db.commit()
        
        # TODO: Trigger Celery task here for Gemini Analysis
        # background_tasks.add_task(analyze_lead, new_lead.id)
        
        logger.info(f"New Lead Saved via Webhook: {lead_data.name} for User: {target_user.email}")

        return {"status": "success", "lead_id": str(new_lead.id)}

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )