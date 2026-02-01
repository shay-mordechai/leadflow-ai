# src/routers/webhooks.py
import logging
import os
import aiofiles
import httpx
import uuid
from typing import Optional
from fastapi import APIRouter, Form, Response

# Twilio TwiML imports
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse

from src.services.ai_engine import ai_engine
from src.config import settings

logger = logging.getLogger("Webhooks")
router = APIRouter()

# Directory for saving voice notes temporarily
STORAGE_PATH = "/tmp/voice_notes"
os.makedirs(STORAGE_PATH, exist_ok=True)

async def download_audio_file(url: str, sender_id: str) -> Optional[str]:
    """
    Downloads an audio file from a URL securely.
    Returns the local file path or None if failed.
    """
    try:
        # Generate a unique filename using UUID to prevent collisions
        filename = f"{sender_id}_{uuid.uuid4().hex[:8]}.ogg"
        file_path = os.path.join(STORAGE_PATH, filename)

        # Configure client with redirects enabled (Crucial for external URLs)
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url)
            
            if resp.status_code == 200:
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(resp.content)
                logger.info(f"✅ Audio downloaded successfully: {file_path}")
                return file_path
            else:
                logger.error(f"❌ Failed to download audio. Status: {resp.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"❌ Download Exception (DNS/Network): {e}")
        return None

# ---------------------------------------------------------
# 1. WhatsApp Handler (Text + Voice Notes)
# ---------------------------------------------------------
@router.post("/whatsapp/twilio")
async def whatsapp_webhook(
    From: str = Form(...),       
    Body: Optional[str] = Form(None),
    MediaUrl0: Optional[str] = Form(None),
    NumMedia: int = Form(0)
):
    """
    Handles incoming WhatsApp messages.
    Supports Text and Audio (Voice Notes).
    """
    sender_phone = From.replace("whatsapp:", "")
    logger.info(f"📩 WhatsApp from {sender_phone}")

    # Mock User Context
    user_context = {"name": "Dana Cohen", "hours_until_class": 20}
    ai_response = {}
    local_audio_path = None

    try:
        # A. Handle Audio (Voice Note) 🎤
        if int(NumMedia) > 0 and MediaUrl0:
            logger.info(f"🎤 Voice Note Detected: {MediaUrl0}")
            
            # Download the file
            local_audio_path = await download_audio_file(MediaUrl0, sender_phone)
            
            if local_audio_path:
                # Analyze Audio with Gemini
                ai_response = await ai_engine.analyze_interaction(
                    audio_path=local_audio_path, 
                    user_context=user_context
                )
            else:
                ai_response = {"reply_text": "סליחה, הייתה בעיה בהורדת ההקלטה."}

        # B. Handle Text Message 💬
        elif Body:
            logger.info(f"💬 Text Detected: {Body}")
            # Analyze Text with Gemini
            ai_response = await ai_engine.analyze_interaction(
                text_input=Body, 
                user_context=user_context
            )
        
        else:
            ai_response = {"reply_text": "הודעה ריקה."}

    except Exception as e:
        logger.error(f"❌ Webhook Logic Error: {e}")
        ai_response = {"reply_text": "תקלה במערכת."}

    finally:
        # Cleanup: Delete the temp audio file to save space
        if local_audio_path and os.path.exists(local_audio_path):
            try:
                os.remove(local_audio_path)
                logger.info(f"🧹 Cleaned up file: {local_audio_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to delete temp file: {cleanup_error}")

    # Prepare TwiML Response
    reply = ai_response.get("reply_text", "תודה.")
    resp = MessagingResponse()
    resp.message(reply)
    
    return Response(content=str(resp), media_type="application/xml")


# ---------------------------------------------------------
# 2. Voice Call Handler (SIP / PSTN)
# ---------------------------------------------------------
@router.post("/voice/incoming")
async def voice_webhook(
    From: str = Form(...),
    To: str = Form(...),
    SpeechResult: Optional[str] = Form(None)
):
    """
    Handles incoming Voice Calls.
    Uses Twilio's <Gather> for Speech-to-Text interaction.
    """
    logger.info(f"📞 Incoming Call from {From} to {To}")
    
    twiml = VoiceResponse()

    if SpeechResult:
        logger.info(f"🗣️ User said: {SpeechResult}")
        try:
            ai_response = await ai_engine.analyze_interaction(text_input=SpeechResult)
            reply_text = ai_response.get("reply_text", "בודקת...")
            twiml.say(reply_text, language="he-IL", voice="alice")
        except Exception as e:
            logger.error(f"❌ Voice Error: {e}")
            twiml.say("תקלה טכנית.", language="he-IL")
    else:
        twiml.say("שלום, כאן הסטודיו של לאה. איך אפשר לעזור?", language="he-IL", voice="alice")

    twiml.gather(
        input="speech", 
        language="he-IL", 
        action="/webhooks/voice/incoming", 
        timeout=4
    )

    return Response(content=str(twiml), media_type="application/xml")