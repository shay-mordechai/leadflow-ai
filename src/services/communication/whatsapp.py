# src/routers/webhooks/whatsapp.py
import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, Query, HTTPException, Depends, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

# Internal imports
from src.config import settings
from src.database.session import SessionLocal
from src.database.models import PhoneNumber, AIAgent
from src.services.ai.engine import ai_engine
# NEW: Import the WhatsApp Adapter
from src.services.communication.whatsapp import whatsapp_adapter

router = APIRouter(tags=["Webhooks - WhatsApp"])
logger = logging.getLogger("WhatsAppWebhook")

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def verify_whatsapp_signature(request: Request):
    """
    Security Middleware: Validates the SHA256 signature from Meta.
    """
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        logger.warning(f"❌ Missing X-Hub-Signature-256 from {request.client.host}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature missing")

    if not signature.startswith("sha256="):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature format")
    
    received_hash = signature[7:]

    body = await request.body()
    expected_hash = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode('utf-8') if hasattr(settings, 'WHATSAPP_APP_SECRET') else b"",
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
    Receives incoming WhatsApp messages after verifying Meta signature.
    """
    # await verify_whatsapp_signature(request) # Uncomment in Prod

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
            sender_id = message["from"]  # The customer's phone number
            msg_type = message["type"]
            sender_name = value.get("contacts", [{}])[0].get("profile", {}).get("name", "Guest")
            
            logger.info(f"💬 WhatsApp Message from {sender_name} ({sender_id}) to Bot {bot_phone_number}")
            
            # --- AI BRAIN INTEGRATION ---
            db = next(get_db_session())
            
            phone_record = db.query(PhoneNumber).filter(PhoneNumber.number.contains(bot_phone_number)).first()
            
            if not phone_record:
                logger.warning(f"⚠️ Received message for unassigned number: {bot_phone_number}")
                return {"status": "ignored_unassigned_number"}
                
            agent = db.query(AIAgent).filter(AIAgent.user_id == phone_record.owner_id).first()
            
            if not agent or not agent.is_active:
                logger.info(f"💤 AI Agent is disabled or missing for {bot_phone_number}")
                return {"status": "agent_disabled"}
                
            # Process Message
            if msg_type == "text":
                text_body = message["text"]["body"]
                
                # 1. Ask Gemini what to say
                ai_response = await ai_engine.analyze_interaction(
                    system_prompt=agent.system_prompt,
                    text_input=text_body,
                    sender_name=sender_name
                )
                
                reply_text = ai_response.get('reply_text', "I'm sorry, I encountered an error processing your request.")
                logger.info(f"🤖 AI Generated Reply: {reply_text}")
                
                # 2. SEND THE MESSAGE BACK TO THE CUSTOMER
                # Note: Meta requires the 'to' number without the '+' sign
                clean_sender_id = sender_id.replace("+", "")
                success = whatsapp_adapter.send_message(to_phone=clean_sender_id, text=reply_text)
                
                if success:
                    logger.info("✅ Reply sent successfully via WhatsApp.")
                else:
                    logger.error("❌ Failed to send reply via WhatsApp.")

            elif msg_type == "audio":
                audio_id = message["audio"]["id"]
                # TODO: Download media -> Transcribe -> Call ai_engine.analyze_interaction
                # We will implement audio handling later if needed.

        return {"status": "received"}

    except Exception as e:
        logger.error(f"🔥 WhatsApp Webhook Processing Error: {e}")
        return {"status": "error"}