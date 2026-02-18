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
# NEW: Import the WhatsApp adapter to send proactive messages
from src.services.communication.whatsapp import whatsapp_adapter

# Initialize Router
router = APIRouter(tags=["Leads Management"])
logger = logging.getLogger(__name__)

# Security: Get Limiter instance from main app state or create new
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
        try:
            uuid_obj = uuid.UUID(user_id)
        except ValueError:
             raise HTTPException(status_code=400, detail="Invalid User ID format")

        # 2. Validate User Exists
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
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
            name=lead_data.name,
            phone_number=lead_data.phone,
            email=lead_data.email, 
            source=LeadSource.LANDING_PAGE,
            status=LeadStatus.NEW
        )
        
        db.add(new_lead)
        db.commit()
        
        logger.info(f"New Lead Saved via Webhook: {lead_data.name} for User: {target_user.email}")

        # ------------------------------------------------------------------
        # 5. SPEED TO LEAD: Proactive WhatsApp Outreach
        # ------------------------------------------------------------------
        try:
            # Clean the phone number (remove +, -, spaces) for Meta API
            clean_phone = ''.join(filter(str.isdigit, lead_data.phone))
            
            # Fetch business name safely
            biz_name = getattr(target_user, "business_name", "העסק שלנו") 
            if not biz_name:
                biz_name = "העסק שלנו"
            
            # Note: In a strict Meta Production environment, this specific string MUST match 
            # a pre-approved Template in the Meta Business Manager to open the 24h window.
            # For MVP/Sandbox, this text will be sent to initiate the conversation.
            intro_text = f"היי {lead_data.name}, תודה שהשארת פרטים! אני המזכירה הווירטואלית של {biz_name}. איך אפשר לעזור לך היום?"
            
            # Send the message
            success = whatsapp_adapter.send_message(to_phone=clean_phone, text=intro_text)
            
            if success:
                logger.info(f"🚀 Speed-to-Lead: Proactive WhatsApp message sent to {clean_phone}")
            else:
                logger.warning(f"⚠️ Speed-to-Lead: Failed to send proactive WhatsApp message to {clean_phone}")
                
        except Exception as wa_err:
            # We catch this so the webhook still returns 201 Created to Zapier/Facebook
            # even if the WhatsApp delivery fails.
            logger.error(f"WhatsApp outreach failed for lead {new_lead.id}: {wa_err}")

        return {"status": "success", "lead_id": str(new_lead.id)}

    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing lead"
        )