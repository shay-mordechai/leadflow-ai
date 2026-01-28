# src/routers/webhooks.py
import logging
import os
import aiofiles
import httpx
from datetime import datetime
from fastapi import APIRouter, Form, Request, Depends
from typing import Optional

from src.services.ai_engine import ai_engine
from src.config import settings

logger = logging.getLogger("Webhooks")
router = APIRouter()

# Directory for saving voice notes
STORAGE_PATH = "/app/storage/voice_notes"
os.makedirs(STORAGE_PATH, exist_ok=True)

@router.post("/whatsapp/twilio")
async def whatsapp_webhook(
    From: str = Form(...),       # Twilio sends Form Data, not JSON
    Body: Optional[str] = Form(None),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
    NumMedia: int = Form(0)
):
    """
    Handles incoming WhatsApp messages from Twilio.
    Supports Text and Voice Notes.
    """
    sender_phone = From.replace("whatsapp:", "")
    logger.info(f"📩 Message from {sender_phone}")

    # 1. Mock Context (Later: Get from DB based on sender_phone)
    # נניח שאנחנו יודעים שהיא רשומה לשיעור מחר
    user_context = {
        "name": "Dana Cohen",
        "upcoming_class": "Pilates - Tomorrow 18:00",
        "hours_until_class": 20  # <--- Less than 24h! Triggers the logic.
    }

    ai_response = {}

    # 2. Handle Voice Note (Audio) 🎤
    if int(NumMedia) > 0 and MediaUrl0:
        logger.info(f"🎤 Voice Note Received: {MediaUrl0}")
        
        # Download the file
        filename = f"{sender_phone}_{int(datetime.now().timestamp())}.ogg"
        file_path = os.path.join(STORAGE_PATH, filename)
        
        async with httpx.AsyncClient() as client:
            # Twilio media requires Basic Auth if configured, usually public with token
            resp = await client.get(MediaUrl0)
            if resp.status_code == 200:
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(resp.content)
                
                # Send to Gemini (Audio Analysis)
                ai_response = await ai_engine.analyze_interaction(
                    audio_path=file_path, 
                    user_context=user_context
                )
            else:
                logger.error("Failed to download audio from Twilio")
                ai_response = {"reply_text": "היתה בעיה עם ההקלטה שלך, אפשר לכתוב?"}

    # 3. Handle Text Message 💬
    elif Body:
        logger.info(f"💬 Text Received: {Body}")
        # Send to Gemini (Text Analysis)
        ai_response = await ai_engine.analyze_interaction(
            text_input=Body, 
            user_context=user_context
        )

    # 4. Log the Result (In production: Send reply back via Twilio)
    reply = ai_response.get("reply_text", "Error processing request")
    action = ai_response.get("action_required", "none")
    
    logger.info(f"🤖 Action: {action} | Reply: {reply}")

    # Twilio expects TwiML (XML) response to reply immediately
    # This is the simplest way to reply without an extra API call
    from twilio.twiml.messaging_response import MessagingResponse
    resp = MessagingResponse()
    resp.message(reply)
    
    return fastapi.Response(content=str(resp), media_type="application/xml")