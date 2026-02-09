# src/routers/webhooks/twilio.py
import logging
from fastapi import APIRouter, Request, Form, Response

# Twilio Helper Library for generating XML responses
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse

router = APIRouter(tags=["Webhooks - Twilio"])
logger = logging.getLogger("TwilioWebhook")

@router.post("/voice")
async def incoming_voice_call(
    From: str = Form(...),
    To: str = Form(...),
    CallSid: str = Form(...)
):
    """
    Handles incoming Voice Calls.
    Returns TwiML to record the caller's message.
    """
    logger.info(f"📞 Incoming Call | From: {From} | To: {To} | SID: {CallSid}")

    resp = VoiceResponse()
    resp.say("Hello. You have reached the LeadFlow AI assistant. Please state your name and reason for calling.", voice="alice")
    resp.record(maxLength=60, playBeep=True, transcribe=False)
    resp.hangup()

    return Response(content=str(resp), media_type="application/xml")


@router.post("/sms")
async def incoming_sms_message(
    From: str = Form(...),
    Body: str = Form(...),
    To: str = Form(...)
):
    """
    Handles incoming SMS.
    """
    logger.info(f"📩 Incoming SMS | From: {From} | Body: {Body}")

    resp = MessagingResponse()
    reply_text = "Thanks for your message! Our AI agent has received it and will get back to you shortly."
    resp.message(reply_text)

    return Response(content=str(resp), media_type="application/xml")