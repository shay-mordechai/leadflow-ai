# src/routers/webhooks.py
import logging
import os
from typing import Optional
from fastapi import APIRouter, Form, Response, BackgroundTasks

# Services - CORRECTED PATHS
from src.services.communication.whatsapp_adapter import whatsapp_adapter
from src.services.ai.engine import ai_engine
from src.services.media.transcription import transcriber 
from src.services.media.pdf_maker import pdf_maker 
from src.services.communication.email import email_service

# Twilio TwiML
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse

logger = logging.getLogger("Webhooks")
router = APIRouter()

# --- Background Worker Function ---
async def process_audio_pipeline(media_url: str, sender_phone: str):
    """
    Background Task:
    1. Download Audio
    2. Transcribe (Local Whisper)
    3. Summarize (Gemini)
    4. Generate PDF
    5. Email PDF to Admin
    """
    logger.info(f"⚙️ Starting background pipeline for {sender_phone}...")
    local_audio_path = None
    pdf_path = None

    try:
        # 1. Download
        local_audio_path = whatsapp_adapter.download_media(media_url)
        if not local_audio_path:
            return

        # 2. Transcribe (Heavy CPU)
        transcription_result = transcriber.transcribe_audio(local_audio_path)
        raw_text = transcription_result.get("text", "")
        
        if not raw_text:
            logger.warning("Empty transcription result.")
            return

        logger.info(f"📝 Transcribed: {raw_text[:30]}...")

        # 3. Summarize
        summary_text = ai_engine.generate_meeting_summary(raw_text)

        # 4. Generate PDF
        safe_phone = sender_phone.replace("+", "")
        pdf_filename = f"summary_{safe_phone}.pdf"
        pdf_path = pdf_maker.create_meeting_summary(summary_text, pdf_filename)

        # 5. Email
        admin_email = "shay.mordechai@proton.me" 
        
        await email_service.send_payment_receipt(
            to_email=admin_email,
            pdf_path=pdf_path
        )

        logger.info("✅ Pipeline completed successfully.")

    except Exception as e:
        logger.error(f"❌ Background pipeline failed: {e}")
    
    finally:
        # Cleanup
        if local_audio_path and os.path.exists(local_audio_path):
            os.remove(local_audio_path)

# ---------------------------------------------------------
# 1. WhatsApp Handler
# ---------------------------------------------------------
@router.post("/whatsapp/twilio")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),       
    Body: Optional[str] = Form(None),
    MediaUrl0: Optional[str] = Form(None),
    NumMedia: int = Form(0),
    MediaContentType0: str = Form(None)
):
    """
    Handles incoming WhatsApp messages via Twilio.
    Triggers background processing for Audio.
    """
    sender_phone = From.replace("whatsapp:", "")
    logger.info(f"📩 WhatsApp from {sender_phone}")

    resp = MessagingResponse()

    # Context for AI
    user_context = {"name": "Client", "business_type": "Consulting"}

    try:
        # A. Handle Audio (Voice Note)
        if int(NumMedia) > 0 and MediaUrl0 and "audio" in (MediaContentType0 or ""):
            logger.info(f"🎤 Voice Note Detected. URL: {MediaUrl0}")
            
            resp.message("🎧 קיבלתי את ההקלטה. אני מתמלל ומסכם... זה ייקח דקה.")
            background_tasks.add_task(process_audio_pipeline, MediaUrl0, sender_phone)
            
            return Response(content=str(resp), media_type="application/xml")

        # B. Handle Text Message
        elif Body:
            ai_response = await ai_engine.analyze_interaction(
                text_input=Body, 
                user_context=user_context
            )
            resp.message(ai_response.get("reply_text", "תודה."))
        
        else:
            resp.message("הודעה ללא תוכן.")

    except Exception as e:
        logger.error(f"❌ Webhook Error: {e}")
        resp.message("תקלה במערכת.")

    return Response(content=str(resp), media_type="application/xml")

# ---------------------------------------------------------
# 2. Voice Call Handler
# ---------------------------------------------------------
@router.post("/voice/incoming")
async def voice_webhook(SpeechResult: Optional[str] = Form(None)):
    """
    Handles incoming Voice Calls (Twilio).
    """
    twiml = VoiceResponse()

    if SpeechResult:
        try:
            ai_response = await ai_engine.analyze_interaction(text_input=SpeechResult)
            reply = ai_response.get("reply_text", "בודקת...")
            twiml.say(reply, language="he-IL", voice="alice")
        except Exception:
            twiml.say("תקלה טכנית.", language="he-IL")
    else:
        twiml.say("שלום, הגעת לבוט החכם. דבר אליי.", language="he-IL", voice="alice")

    twiml.gather(input="speech", language="he-IL", action="/webhooks/voice/incoming", timeout=4)
    return Response(content=str(twiml), media_type="application/xml")