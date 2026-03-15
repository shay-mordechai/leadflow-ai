# src/routers/webhooks/whatsapp.py
import logging
import hmac
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo 
from fastapi import APIRouter, Request, Query, HTTPException, Depends, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

# Internal imports
from src.config import settings
from src.database.session import SessionLocal
from src.database.models import PhoneNumber, AIAgent, User, PlanTier, Lead, LeadStatus, Message, LeadSource
from src.services.ai.engine import ai_engine
from src.services.communication.whatsapp import whatsapp_adapter 

router = APIRouter(tags=["Webhooks - WhatsApp"])
logger = logging.getLogger("WhatsAppWebhook")

STARTER_MESSAGE_LIMIT = 10
PRO_MESSAGE_LIMIT = 2000

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def verify_whatsapp_signature(request: Request):
    """
    Security Middleware: Validates the SHA256 signature from Meta.
    Ensures the request originated from Facebook/Meta servers.
    """
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        logger.warning(f"❌ Missing X-Hub-Signature-256 from {request.client.host}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature missing")

    if not signature.startswith("sha256="):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature format")
    
    received_hash = signature[7:]
    body = await request.body()
    
    secret = getattr(settings, 'WHATSAPP_APP_SECRET', "")
    expected_hash = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received_hash, expected_hash):
        logger.error(f"❌ SECURITY ALERT: Invalid WhatsApp signature from {request.client.host}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")


@router.get("/")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
):
    """Meta (Facebook) Verification Handshake."""
    verify_token = settings.WHATSAPP_VERIFY_TOKEN

    if mode == "subscribe" and token == verify_token:
        logger.info("✅ WhatsApp Webhook Verified successfully.")
        return PlainTextResponse(content=challenge)
    
    logger.warning("❌ WhatsApp Verification Failed: Invalid Token.")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/")
async def whatsapp_event_listener(request: Request):
    """
    Receives incoming Meta WhatsApp messages.
    Supports Human Takeover logic by checking bot_active status.
    """
    try:
        data = await request.json()
        
        if not data.get("entry"):
            return {"status": "no_entry"}

        entry = data["entry"][0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        metadata = value.get("metadata", {})
        bot_phone_number = metadata.get("display_phone_number")
        
        if "messages" in value:
            message = value["messages"][0]
            sender_id = message["from"]
            msg_type = message["type"]
            sender_name = value.get("contacts", [{}])[0].get("profile", {}).get("name", "Guest")
            
            logger.info(f"💬 Authenticated WhatsApp Message from {sender_name} ({sender_id}) to Bot {bot_phone_number}")
            
            db = next(get_db_session())
            
            phone_record = db.query(PhoneNumber).filter(PhoneNumber.number.contains(bot_phone_number)).first()
            if not phone_record:
                logger.warning(f"⚠️ Received message for unassigned number: {bot_phone_number}")
                return {"status": "ignored_unassigned_number"}
                
            agent = db.query(AIAgent).filter(AIAgent.user_id == phone_record.owner_id).first()
            user = db.query(User).filter(User.id == phone_record.owner_id).first()
            
            if not agent or not agent.is_active or not user:
                logger.info(f"💤 AI Agent is disabled or missing for {bot_phone_number}")
                return {"status": "agent_disabled"}
            
            # ------------------------------------------------------------------
            # 1. Lead Resolution (Robust)
            # ------------------------------------------------------------------
            clean_sender_id = sender_id.replace("+", "")
            
            lead_record = db.query(Lead).filter(
                Lead.user_id == user.id,
                Lead.phone_number.like(f"%{clean_sender_id[-9:]}%")
            ).first()
            
            if not lead_record:
                lead_record = Lead(user_id=user.id, name=sender_name, phone_number=clean_sender_id, source=LeadSource.WHATSAPP)
                db.add(lead_record)
                db.commit()
                db.refresh(lead_record)

            if lead_record.status == LeadStatus.NEW:
                logger.info(f"🛑 Stopping follow-ups for lead {lead_record.id}. Status changed to IN_PROGRESS.")
                lead_record.status = LeadStatus.IN_PROGRESS
                lead_record.needs_followup = False
                db.commit()

            # ------------------------------------------------------------------
            # 2. Save Message & Human Takeover Check
            # ------------------------------------------------------------------
            if msg_type == "text":
                text_body = message["text"]["body"]
                
                # FIX: Save incoming message to history regardless of bot status
                db.add(Message(lead_id=lead_record.id, sender_type="user", content=text_body))
                db.commit()

                # FIX: Human Takeover check AFTER saving message
                if not lead_record.bot_active:
                    logger.info(f"🛑 Muted lead {clean_sender_id} (Human Takeover) - Message saved, skipping AI.")
                    return {"status": "muted"}

                # Check Usage Limits
                max_limit = PRO_MESSAGE_LIMIT if user.plan_tier == PlanTier.PRO else STARTER_MESSAGE_LIMIT
                if user.monthly_ai_messages >= max_limit:
                    logger.warning(f"🚫 User {user.email} exceeded AI message limit.")
                    limit_reply = "We apologize, but this automated assistant is temporarily unavailable. A human representative will contact you soon."
                    whatsapp_adapter.send_message(to_phone=clean_sender_id, text=limit_reply)
                    return {"status": "limit_exceeded"}

                # --- AI Processing ---
                israel_tz = ZoneInfo("Asia/Jerusalem")
                current_time_il = datetime.now(israel_tz).strftime("%A, %Y-%m-%d %H:%M:%S")
                time_aware_system_prompt = f"{agent.system_prompt}\n\n[SYSTEM CLOCK]\nThe current Date and Time in Israel is: {current_time_il}"
                
                ai_response = await ai_engine.analyze_interaction(
                    system_prompt=time_aware_system_prompt,
                    text_input=text_body,
                    sender_name=sender_name
                )
                
                reply_text = ai_response.get('reply_text', "I'm sorry, I encountered an error processing your request.")
                logger.info(f"🤖 AI Generated Reply: {reply_text}")
                
                user.monthly_ai_messages += 1
                db.commit()
                
                # Handoff Detection
                handoff_keys = ["נציג", "אנושי", "מנהל", "human", "representative", "manager"]
                if ai_response.get("needs_human_escalation") or any(k in text_body.lower() for k in handoff_keys):
                    logger.info(f"🚨 Handoff triggered for {clean_sender_id}")
                    lead_record.bot_active = False
                    lead_record.requires_human = True
                    db.commit()
                
                # Save & Send Reply
                db.add(Message(lead_id=lead_record.id, sender_type="bot", content=reply_text))
                db.commit()
                whatsapp_adapter.send_message(to_phone=clean_sender_id, text=reply_text)

            elif msg_type == "audio":
                logger.info("🎤 Audio message received via Meta API. (Routing not yet fully implemented for Meta Audio)")

        return {"status": "received"}

    except Exception as e:
        logger.error(f"🔥 WhatsApp Webhook Processing Error: {str(e)}")
        return {"status": "error"}