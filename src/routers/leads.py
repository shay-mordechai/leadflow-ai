# src/routers/leads.py
import logging
import uuid
from uuid import UUID
import hashlib
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

# Security: Rate Limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.database.session import get_db
# TIER 1 RELIABILITY: Imported WebhookDLQ and WebhookProvider for Fail-Safe queue
from src.database.models import Lead, User, LeadSource, LeadStatus, WebhookDLQ, WebhookProvider
from src.security.dependencies import get_current_user
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
    source: str = Field(default="LANDING_PAGE", max_length=50) 
    # NEW: Allow Meta/Zapier to pass their unique event ID to prevent duplicates
    idempotency_key: Optional[str] = Field(None, description="Unique event ID from Zapier/Make to prevent duplicates")

class LeadResponse(BaseModel):
    id: UUID
    name: str
    phone_number: str
    email: Optional[str] = None
    status: str
    source: str
    bot_active: bool = True
    summary_text: Optional[str] = None
    suggested_reply: Optional[str] = None
    ai_rating: Optional[int] = None      
    ai_feedback_note: Optional[str] = None 
    created_at: datetime
    
    model_config = {"from_attributes": True}

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

# --- NEW: AI Feedback Loop Endpoint ---
@router.post("/{lead_id}/feedback")
@limiter.limit("20/minute") # Security: Prevent feedback spam
async def submit_lead_feedback(
    request: Request,
    lead_id: str, 
    rating: int = Query(..., description="1 for Like, -1 for Dislike"),
    note: Optional[str] = Query(None, description="Optional text feedback"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    SECURE ENDPOINT: Submit AI feedback for a specific lead's interaction.
    Allows users to rate the AI's performance (👍/👎).
    """
    # 1. Security: Find the lead and verify ownership (IDOR protection)
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == current_user.id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if rating not in [1, -1, 0]:
        raise HTTPException(status_code=400, detail="Invalid rating value. Must be 1 or -1.")

    # 2. Update feedback
    lead.ai_rating = rating
    if note:
        lead.ai_feedback_note = note
        
    db.commit()
    logger.info(f"🧠 AI Feedback recorded for Lead {lead_id} by User {current_user.email}: Rating {rating}")
    
    return {"status": "success", "message": "Feedback recorded. The AI is learning!"}

@router.post("/webhook/{user_id}", status_code=status.HTTP_200_OK)
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
    Mitigation: Rate Limited. Validates UUID format. Idempotency Key protection.
    Reliability: Wrapped in DLQ logic to prevent data loss on crashes.
    """
    raw_payload = {}
    try:
        # Attempt to capture raw request JSON for DLQ fallback (Fail-Safe)
        raw_payload = await request.json()
    except Exception:
        pass # Ignore parsing errors here, we'll use Pydantic model dump instead

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

        # 3. SECURITY: Idempotency Check (The "Retry Storm" Shield)
        if lead_data.idempotency_key:
            idemp_key = lead_data.idempotency_key
        else:
            raw_key = f"{lead_data.phone}-{lead_data.source}-{datetime.utcnow().strftime('%Y-%m-%d')}"
            idemp_key = hashlib.md5(raw_key.encode()).hexdigest()

        existing_lead = db.query(Lead).filter(
            Lead.user_id == target_user.id,
            Lead.idempotency_key == idemp_key
        ).first()

        if existing_lead:
            logger.info(f"🛡️ Idempotency Shield: Caught duplicate lead {lead_data.phone}. Returning 200 OK to stop retries.")
            return {"status": "success", "message": "Lead already processed", "lead_id": str(existing_lead.id)}

        # 4. Create DB Entry 
        safe_source = lead_data.source.upper() if lead_data.source else "LANDING_PAGE"
        
        new_lead = Lead(
            user_id=target_user.id,
            name=lead_data.name,
            phone_number=lead_data.phone,
            email=lead_data.email, 
            source=safe_source,
            status=LeadStatus.NEW,
            idempotency_key=idemp_key 
        )
        
        db.add(new_lead)
        db.commit()
        
        logger.info(f"✅ New Lead Saved via Webhook: {lead_data.name} for User: {target_user.email}")

        # 5. SPEED TO LEAD: Proactive WhatsApp Outreach
        try:
            clean_phone = ''.join(filter(str.isdigit, lead_data.phone))
            biz_name = getattr(target_user, "business_name", "העסק שלנו") 
            if not biz_name:
                biz_name = "העסק שלנו"
            
            intro_text = f"היי {lead_data.name}, תודה שהשארת פרטים! אני המזכירה הווירטואלית של {biz_name}. איך אפשר לעזור לך היום?"
            
            success = whatsapp_adapter.send_message(to_phone=clean_phone, text=intro_text)
            
            if success:
                logger.info(f"🚀 Speed-to-Lead: Proactive WhatsApp message sent to {clean_phone}")
            else:
                logger.warning(f"⚠️ Speed-to-Lead: Failed to send proactive WhatsApp message to {clean_phone}")
                
        except Exception as wa_err:
            logger.error(f"WhatsApp outreach failed for lead {new_lead.id}: {wa_err}")

        return {"status": "success", "lead_id": str(new_lead.id)}

    except HTTPException as he:
        raise he
    except Exception as e:
        # Rollback the broken transaction
        db.rollback()
        logger.error(f"Error processing webhook: {str(e)}")
        
        # --- TIER 1 RELIABILITY: DEAD LETTER QUEUE (DLQ) ---
        try:
            fallback_payload = raw_payload if raw_payload else (lead_data.model_dump(mode='json') if lead_data else {"raw": "Unknown payload"})
            
            dlq_entry = WebhookDLQ(
                provider=WebhookProvider.CUSTOM,
                payload=fallback_payload,
                error_reason=str(e)
            )
            db.add(dlq_entry)
            db.commit()
            logger.warning(f"🚨 Webhook failed but saved to Dead Letter Queue (DLQ) for User {user_id}. Lead Data saved for manual retry.")
        except Exception as dlq_err:
            logger.critical(f"🔥 FATAL: Could not save failed webhook to DLQ. Data Loss Risk! Error: {str(dlq_err)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing lead. Our team has been notified."
        )