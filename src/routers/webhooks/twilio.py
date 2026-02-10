# src/routers/webhooks/twilio.py
import logging
from fastapi import APIRouter, Request, Form, Response, HTTPException, status
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse

# Internal imports
from src.config import settings

router = APIRouter(tags=["Webhooks - Twilio"])
logger = logging.getLogger("TwilioWebhook")

async def verify_twilio_signature(request: Request):
    """
    Security Middleware: Validates that the incoming request is genuinely from Twilio.
    Prevents Request Spoofing and unauthorized TwiML execution.
    """
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    
    # 1. Get the signature from the header
    signature = request.headers.get("X-Twilio-Signature", "")
    
    # 2. Twilio signs the full URL including protocol and query params
    # Ensure settings.BASE_URL is set correctly (e.g., https://my-leads.app)
    url = str(request.url)
    
    # 3. Twilio signs the POST form data
    form_data = await request.form()
    
    if not validator.validate(url, dict(form_data), signature):
        logger.warning(f"❌ SECURITY ALERT: Fake Twilio Request blocked from IP: {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature"
        )

@router.post("/voice")
async def incoming_voice_call(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    CallSid: str = Form(...)
):
    """
    Handles incoming Voice Calls after validating the signature.
    """
    # SECURITY CHECK
    await verify_twilio_signature(request)

    logger.info(f"📞 Authenticated Call | From: {From} | SID: {CallSid}")

    resp = VoiceResponse()
    resp.say("Hello. You have reached the LeadFlow AI assistant. Please state your name and reason for calling.", voice="alice")
    
    # Security Note: Limit recording length to prevent storage exhaustion attacks
    resp.record(maxLength=60, playBeep=True, transcribe=False)
    resp.hangup()

    return Response(content=str(resp), media_type="application/xml")


@router.post("/sms")
async def incoming_sms_message(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    To: str = Form(...)
):
    """
    Handles incoming SMS after validating the signature.
    """
    # SECURITY CHECK
    await verify_twilio_signature(request)

    logger.info(f"📩 Authenticated SMS | From: {From}")

    resp = MessagingResponse()
    reply_text = "Thanks for your message! Our AI agent has received it and will get back to you shortly."
    resp.message(reply_text)

    return Response(content=str(resp), media_type="application/xml")