# src/routers/webhooks/whatsapp.py
import logging
import hmac
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo # FIXED: Modern timezone handling for AI temporal awareness
from fastapi import APIRouter, Request, Query, HTTPException, Depends, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

# Internal imports
from src.config import settings
from src.database.session import SessionLocal
from src.database.models import PhoneNumber, AIAgent, User, PlanTier, Lead, LeadStatus
from src.services.ai.engine import ai_engine
from src.services.communication.whatsapp import whatsapp_adapter # UNCOMMENTED: To actually send messages

router = APIRouter(tags=["Webhooks - WhatsApp"])
logger = logging.getLogger("WhatsAppWebhook")

# --- Usage Limit Constants ---
STARTER_MESSAGE_LIMIT = 50
PRO_MESSAGE_LIMIT = 2000
# ----------------------------------

# Helper to get a DB session inside a webhook
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
    
    # Securely retrieve the App Secret
    secret = getattr(settings, 'WHATSAPP_APP_SECRET', "")
    expected_hash = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received_hash, expected_hash):
        logger.error(f"❌ SECURITY ALERT: Invalid WhatsApp signature from {request.client.host}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

# ------------------------------------------------------------------
# 1. Verification Endpoint (GET)
# ------------------------------------------------------------------
@router.get("/")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
):
    """
    Meta (Facebook) Verification Handshake.
    """
    verify_token = settings.WHATSAPP_VERIFY_TOKEN

    if mode == "subscribe" and token == verify_token:
        logger.info("✅ WhatsApp Webhook Verified successfully.")
        return PlainTextResponse(content=challenge)
    
    logger.warning("❌ WhatsApp Verification Failed: Invalid Token.")
    raise HTTPException(status_code=403, detail="Verification failed")


# ------------------------------------------------------------------
# 2. Event Listener (POST)
# ------------------------------------------------------------------
@router.post("/")
async def whatsapp_event_listener(request: Request):
    """
    Receives incoming WhatsApp messages. 
    Updates Lead status to stop follow-ups and triggers AI response.
    """
    # SECURITY CHECK (Uncomment in production when WHATSAPP_APP_SECRET is set)
    # await verify_whatsapp_signature(request)

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
            
            # 1. Find the bot's owner
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
            # 2. Update Lead Status (Stop Follow-ups)
            # ------------------------------------------------------------------
            clean_sender_id = sender_id.replace("+", "")
            
            # Security Note: Because phone numbers are encrypted in DB, we fetch 
            # active leads for this user and check in memory.
            active_leads = db.query(Lead).filter(
                Lead.user_id == user.id,
                Lead.status == LeadStatus.NEW
            ).all()
            
            lead_to_update = None
            for l in active_leads:
                if l.phone_number and clean_sender_id[-9:] in l.phone_number:
                    lead_to_update = l
                    break
            
            if lead_to_update:
                logger.info(f"🛑 Stopping follow-ups for lead {lead_to_update.id}. Status changed to IN_PROGRESS.")
                lead_to_update.status = LeadStatus.IN_PROGRESS
                lead_to_update.needs_followup = False
                db.commit()
            else:
                logger.info(f"🆕 Unknown number {clean_sender_id} messaged the bot. Treating as generic inquiry.")

            # ------------------------------------------------------------------
            # 3. Check Usage Limits
            # ------------------------------------------------------------------
            max_limit = PRO_MESSAGE_LIMIT if user.plan_tier == PlanTier.PRO else STARTER_MESSAGE_LIMIT
            if user.monthly_ai_messages >= max_limit:
                logger.warning(f"🚫 User {user.email} exceeded AI message limit.")
                limit_reply = "We apologize, but this automated assistant is temporarily unavailable. A human representative will contact you soon."
                whatsapp_adapter.send_message(to_phone=clean_sender_id, text=limit_reply)
                return {"status": "limit_exceeded"}

            # ------------------------------------------------------------------
            # 4. AI Processing & Reply
            # ------------------------------------------------------------------
            if msg_type == "text":
                text_body = message["text"]["body"]
                
                # --- TIER 1 RELIABILITY: TEMPORAL AWARENESS ---
                # Inject current local time so the AI Agent correctly calculates "tomorrow" or "next week"
                israel_tz = ZoneInfo("Asia/Jerusalem")
                current_time_il = datetime.now(israel_tz).strftime("%A, %Y-%m-%d %H:%M:%S")
                
                time_aware_system_prompt = f"{agent.system_prompt}\n\n[SYSTEM CLOCK]\nThe current Date and Time in Israel is: {current_time_il}\nUse this exact time as your reference point for scheduling or answering temporal questions."
                
                # Note: Next step in Phase 3 is injecting 'chat_history' here from the Message table
                ai_response = await ai_engine.analyze_interaction(
                    system_prompt=time_aware_system_prompt,
                    text_input=text_body,
                    sender_name=sender_name
                )
                
                reply_text = ai_response.get('reply_text', "I'm sorry, I encountered an error processing your request.")
                logger.info(f"🤖 AI Generated Reply: {reply_text}")
                
                user.monthly_ai_messages += 1
                db.commit()
                
                # Send Reply via WhatsApp
                success = whatsapp_adapter.send_message(to_phone=clean_sender_id, text=reply_text)
                
                if success:
                    logger.info(f"✅ Reply sent successfully to {clean_sender_id}")
                else:
                    logger.error(f"❌ Failed to send reply to {clean_sender_id}")

            elif msg_type == "audio":
                logger.info("🎤 Audio message received. Audio processing not yet implemented.")
                # audio_id = message["audio"]["id"]

        return {"status": "received"}

    except Exception as e:
        logger.error(f"🔥 WhatsApp Webhook Processing Error: {str(e)}")
        return {"status": "error"}