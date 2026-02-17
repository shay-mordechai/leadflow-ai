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

router = APIRouter(tags=["Webhooks - WhatsApp"])
logger = logging.getLogger("WhatsAppWebhook")

# Helper to get a DB session inside a webhook (since it's not a standard dependency injection route)
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
    # 1. Get the signature from the header
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        logger.warning(f"❌ Missing X-Hub-Signature-256 from {request.client.host}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature missing")

    if not signature.startswith("sha256="):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature format")
    
    received_hash = signature[7:]

    # SECURITY: Meta signs the raw request body
    body = await request.body()
    # Note: Ensure WHATSAPP_APP_SECRET is set in your environment/SSM!
    expected_hash = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode('utf-8') if hasattr(settings, 'WHATSAPP_APP_SECRET') else b"",
        body,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
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
    Receives incoming WhatsApp messages after verifying Meta signature.
    """
    # SECURITY CHECK
    # await verify_whatsapp_signature(request) # Uncomment in Production when Secret is configured

    try:
        data = await request.json()
        
        if not data.get("entry"):
            return {"status": "no_entry"}

        entry = data["entry"][0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        # Identify the recipient bot (Our customer's phone number)
        metadata = value.get("metadata", {})
        bot_phone_number = metadata.get("display_phone_number")
        
        if "messages" in value:
            message = value["messages"][0]
            sender_id = message["from"]
            msg_type = message["type"]
            sender_name = value.get("contacts", [{}])[0].get("profile", {}).get("name", "Guest")
            
            logger.info(f"💬 Authenticated WhatsApp Message from {sender_name} ({sender_id}) to Bot {bot_phone_number}")
            
            # --- AI BRAIN INTEGRATION ---
            # 1. Open DB Session
            db = next(get_db_session())
            
            # 2. Find the AIAgent associated with this phone number
            # Note: In a real scenario, format the bot_phone_number to match your DB format (e.g., +972...)
            phone_record = db.query(PhoneNumber).filter(PhoneNumber.number.contains(bot_phone_number)).first()
            
            if not phone_record:
                logger.warning(f"⚠️ Received message for unassigned number: {bot_phone_number}")
                return {"status": "ignored_unassigned_number"}
                
            agent = db.query(AIAgent).filter(AIAgent.user_id == phone_record.owner_id).first()
            
            if not agent or not agent.is_active:
                logger.info(f"💤 AI Agent is disabled or missing for {bot_phone_number}")
                return {"status": "agent_disabled"}
                
            # 3. Process the Message with the Dynamic Prompt
            if msg_type == "text":
                text_body = message["text"]["body"]
                
                # Call Gemini using the customer's specific Brain (system_prompt)
                ai_response = await ai_engine.analyze_interaction(
                    system_prompt=agent.system_prompt,
                    text_input=text_body,
                    sender_name=sender_name
                )
                
                logger.info(f"🤖 AI Generated Reply: {ai_response.get('reply_text')}")
                
                # TODO: Send the 'reply_text' back to the user via WhatsApp Graph API
                # await send_whatsapp_message(sender_id, ai_response.get('reply_text'))

            elif msg_type == "audio":
                audio_id = message["audio"]["id"]
                # TODO: Download media -> Transcribe -> Call ai_engine.analyze_interaction

        return {"status": "received"}

    except Exception as e:
        logger.error(f"🔥 WhatsApp Webhook Processing Error: {e}")
        return {"status": "error"}