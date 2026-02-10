# src/routers/leads.py
import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

# Security: Rate Limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.database.session import get_db
from src.database.models import Lead, User, LeadSource, LeadStatus
from src.security.dependencies import get_current_user

# Initialize Router
router = APIRouter(tags=["Leads Management"])
logger = logging.getLogger(__name__)

# Security: Get Limiter instance from main app state or create new
# (Assuming limiter is passed via dependency injection or global state in a real app structure)
# For this snippet, we assume a global limiter is available or imported from main
# NOTE: In a circular import scenario, move limiter creation to a separate `src/core/limiter.py` file.
# For now, we use a placeholder to show where it goes.
limiter = Limiter(key_func=get_remote_address) 

# --- Schemas ---

class PagixLead(BaseModel):
    """
    Schema for incoming webhook data.
    Security: Strict length checks to prevent buffer overflows/DB spam.
    """
    name: str = Field(..., min_length=2, max_length=100, description="Lead's full name")
    phone: str = Field(..., min_length=9, max_length=20, description="Lead's phone number")
    email: Optional[EmailStr] = None
    source: str = Field(default="pagix_landing_page", max_length=50)

class LeadResponse(BaseModel):
    id: str
    name: str
    phone_number: str
    email: Optional[str] = None
    status: str
    summary_text: Optional[str] = None
    suggested_reply: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# --- Routes ---

@router.get("/", response_model=List[LeadResponse])
@limiter.limit("60/minute") # Security: Prevent scraping (1 req/sec)
async def get_my_leads(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    SECURE ENDPOINT: Returns leads ONLY for the logged-in user.
    """
    # Security: IDOR Protection
    # We deliberately DO NOT accept 'user_id' as a parameter. 
    # We use the token (current_user) as the source of truth.
    query = db.query(Lead).filter(Lead.user_id == current_user.id)
    
    leads = query.order_by(Lead.created_at.desc()).offset(offset).limit(limit).all()
    
    return leads

@router.post("/webhook/{user_id}", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute") # Security: Prevent spam attack via public webhook
async def receive_external_lead(
    request: Request,
    user_id: str,
    lead_data: PagixLead, 
    db: Session = Depends(get_db)
):
    """
    Webhook Endpoint.
    Security Risks: Public endpoint.
    Mitigation: Rate Limited. Validates UUID format.
    """
    try:
        # 1. Security: Validate UUID format
        # Prevents SQL injection attempts via URL or processing errors
        try:
            uuid_obj = uuid.UUID(user_id)
        except ValueError:
             raise HTTPException(status_code=400, detail="Invalid User ID format")

        # 2. Validate User Exists
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
             # Security: Do not reveal too much info, but 404 is acceptable here
             logger.warning(f"Webhook failed: User ID {user_id} not found.")
             raise HTTPException(status_code=404, detail="Target user not found")

        # 3. Duplicate Check
        existing_lead = db.query(Lead).filter(
            Lead.user_id == target_user.id,
            Lead.phone_number == lead_data.phone,
            Lead.status == LeadStatus.NEW
        ).first()

        if existing_lead:
            logger.info(f"Skipping duplicate lead {lead_data.phone} for user {user_id}")
            return {"status": "ignored", "message": "Lead already exists"}

        # 4. Create DB Entry
        new_lead = Lead(
            user_id=target_user.id,
            name=lead_data.name, # Encrypted via Model logic
            phone_number=lead_data.phone, # Encrypted via Model logic
            email=lead_data.email, 
            source=LeadSource.LANDING_PAGE,
            status=LeadStatus.NEW
        )
        
        db.add(new_lead)
        db.commit()
        
        logger.info(f"New Lead Saved via Webhook: {lead_data.name} for User: {target_user.email}")
        return {"status": "success", "lead_id": str(new_lead.id)}

    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing webhook: {str(e)}")
        # Security: Generic Error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing lead"
        )