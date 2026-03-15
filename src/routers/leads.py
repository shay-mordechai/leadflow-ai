# src/routers/leads.py
import logging
import uuid
from uuid import UUID
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

# Security: Rate Limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.database.session import get_db
# FIXED: Added 'Message' to imports for Manual Message logging
from src.database.models import Lead, User, LeadSource, LeadStatus, WebhookDLQ, WebhookProvider, Message
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

# NEW: Schemas for Human Takeover
class ManualMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Text content of the manual message")

class BotStatusRequest(BaseModel):
    bot_active: bool = Field(..., description="True to enable AI, False to mute (Human Takeover)")

# --- Routes ---

@router.get("/", response_model=List[LeadResponse])
@limiter.limit("60/minute") 
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
    query = db.query(Lead).filter(Lead.user_id == current_user.id)
    leads = query.order_by(Lead.created_at.desc()).offset(offset).limit(limit).all()
    return leads

# --- HUMAN TAKEOVER ENDPOINTS ---

@router.patch("/{lead_id}/bot-status")
@limiter.limit("30/minute")
async def toggle_bot_status(
    request: Request,
    lead_id: UUID,
    data: BotStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    SECURE ENDPOINT: Toggles the AI bot on/off for a specific lead.
    When off, the bot will not respond to incoming WhatsApp messages.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    lead.bot_active = data.bot_active
    # If the bot is turned back on, we remove the "requires human" flag
    if data.bot_active:
        lead.requires_human = False
        
    db.commit()
    
    status_msg = "פעיל" if data.bot_active else "מושתק (Human Takeover)"
    logger.info(f"Bot status for Lead {lead_id} changed to {data.bot_active} by {current_user.email}")
    return {"success": True, "bot_active": lead.bot_active, "message": f"הבוט כעת {status_msg}"}

@router.post("/{lead_id}/send-message")
@limiter.limit("30/minute")
async def send_manual_message(
    request: Request,
    lead_id: UUID,
    data: ManualMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    SECURE ENDPOINT: Sends a manual WhatsApp message to the lead.
    Automatically disables the bot for this lead to prevent AI interference.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    try:
        # 1. Clean the phone number and send via WhatsApp Adapter
        clean_phone = ''.join(filter(str.isdigit, lead.phone_number))
        success = whatsapp_adapter.send_message(to_phone=clean_phone, text=data.content)
        
        if not success:
            raise Exception("Communication provider returned failure")

        # 2. Log the manual message in the database as 'human'
        new_msg = Message(
            lead_id=lead.id,
            sender_type="human", 
            content=data.content
        )
        db.add(new_msg)
        
        # 3. Disable the bot automatically (Human Takeover)
        lead.bot_active = False
        lead.requires_human = False 
        
        db.commit()
        logger.info(f"👤 Manual message sent to {clean_phone} by {current_user.email}. Bot muted.")
        
        return {"success": True, "message": "הודעה נשלחה בהצלחה והבוט הושתק."}

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to send manual message: {e}")
        raise HTTPException(status_code=500, detail="שגיאה בשליחת הודעה. ייתכן ואין לך מספר מחובר.")

# --- OTHER ENDPOINTS (Feedback & Webhooks) ---

@router.post("/{lead_id}/feedback")
@limiter.limit("20/minute")
async def submit_lead_feedback(
    request: Request,
    lead_id: str, 
    rating: int = Query(..., description="1 for Like, -1 for Dislike"),
    note: Optional[str] = Query(None, description="Optional text feedback"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if rating not in [1, -1, 0]:
        raise HTTPException(status_code=400, detail="Invalid rating value. Must be 1 or -1.")

    lead.ai_rating = rating
    if note: lead.ai_feedback_note = note
    db.commit()
    logger.info(f"🧠 AI Feedback recorded for Lead {lead_id} by User {current_user.email}: Rating {rating}")
    return {"status": "success", "message": "Feedback recorded. The AI is learning!"}

@router.post("/webhook/{user_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def receive_external_lead(
    request: Request,
    user_id: str,
    lead_data: PagixLead, 
    db: Session = Depends(get_db)
):
    raw_payload = {}
    try:
        raw_payload = await request.json()
    except Exception:
        pass

    try:
        try: uuid_obj = uuid.UUID(user_id)
        except ValueError: raise HTTPException(status_code=400, detail="Invalid User ID format")

        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
             logger.warning(f"Webhook failed: User ID {user_id} not found.")
             raise HTTPException(status_code=404, detail="Target user not found")

        if lead_data.idempotency_key:
            idemp_key = lead_data.idempotency_key
        else:
            raw_key = f"{lead_data.phone}-{lead_data.source}-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
            idemp_key = hashlib.md5(raw_key.encode()).hexdigest()

        existing_lead = db.query(Lead).filter(
            Lead.user_id == target_user.id,
            Lead.idempotency_key == idemp_key
        ).first()

        if existing_lead:
            logger.info(f"🛡️ Idempotency Shield: Caught duplicate lead {lead_data.phone}.")
            return {"status": "success", "message": "Lead already processed", "lead_id": str(existing_lead.id)}

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

        try:
            clean_phone = ''.join(filter(str.isdigit, lead_data.phone))
            biz_name = getattr(target_user, "business_name", "העסק שלנו") or "העסק שלנו"
            intro_text = f"היי {lead_data.name}, תודה שהשארת פרטים! אני המזכירה הווירטואלית של {biz_name}. איך אפשר לעזור לך היום?"
            success = whatsapp_adapter.send_message(to_phone=clean_phone, text=intro_text)
            if success: logger.info(f"🚀 Speed-to-Lead: Proactive message sent to {clean_phone}")
        except Exception as wa_err:
            logger.error(f"WhatsApp outreach failed for lead {new_lead.id}: {wa_err}")

        return {"status": "success", "lead_id": str(new_lead.id)}

    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing webhook: {str(e)}")
        try:
            fallback_payload = raw_payload if raw_payload else (lead_data.model_dump(mode='json') if lead_data else {"raw": "Unknown"})
            dlq_entry = WebhookDLQ(provider=WebhookProvider.CUSTOM, payload=fallback_payload, error_reason=str(e))
            db.add(dlq_entry)
            db.commit()
        except Exception as dlq_err:
            logger.critical(f"🔥 FATAL: Could not save failed webhook to DLQ. Error: {str(dlq_err)}")

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error processing lead.")