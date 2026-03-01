# src/routers/webhooks/twilio.py
import logging
import asyncio
from fastapi import APIRouter, Request, Form, Response, HTTPException, status, Depends
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse

# Internal imports
from src.config import settings
from src.database.session import get_db
from src.database.models import PhoneNumber, Lead, User
from src.services.ai.engine import ai_engine
from src.services.communication.whatsapp import whatsapp_adapter

router = APIRouter(tags=["Webhooks - Twilio"])
logger = logging.getLogger("TwilioWebhook")

async def verify_twilio_signature(request: Request):
    """
    Security Middleware: Validates that the incoming request is genuinely from Twilio.
    """
    if not settings.TWILIO_AUTH_TOKEN:
        logger.warning("⚠️ Skipping Twilio Signature Verification: Auth Token Missing (MOCK MODE)")
        return True

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    signature = request.headers.get("X-Twilio-Signature", "")
    
    # Workaround for proxy/tunnel setups where the scheme might arrive as HTTP instead of HTTPS
    url = str(request.url).replace("http://", "https://") if "my-leads.app" in str(request.url) else str(request.url)
    form_data = await request.form()
    
    if not validator.validate(url, dict(form_data), signature):
        logger.warning(f"❌ SECURITY ALERT: Fake Twilio Request blocked from IP: {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature"
        )
    return True

@router.post("/voice")
async def incoming_voice_call(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    CallSid: str = Form(...)
):
    """Handles incoming Voice Calls (Placeholder for Future IVR)."""
    await verify_twilio_signature(request)
    logger.info(f"📞 Authenticated Call | From: {From} | SID: {CallSid}")

    resp = VoiceResponse()
    resp.say("Hello. You have reached the LeadFlow AI assistant.", voice="alice")
    resp.record(maxLength=60, playBeep=True, transcribe=False)
    resp.hangup()

    return Response(content=str(resp), media_type="application/xml")

@router.post("/sms")
async def incoming_sms_message(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    To: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Handles incoming SMS and WhatsApp messages from Twilio.
    Acts as the main brain for answering leads dynamically.
    """
    await verify_twilio_signature(request)
    logger.info(f"📩 Incoming Message | From: {From} | To: {To} | Body: {Body}")

    # 1. Clean the 'To' and 'From' numbers (Twilio prepends 'whatsapp:' for WA messages)
    clean_to = To.replace("whatsapp:", "").strip()
    clean_from = From.replace("whatsapp:", "").strip()

    # 2. Identify the Business (Who does this Twilio number belong to?)
    phone_record = db.query(PhoneNumber).filter(PhoneNumber.number == clean_to, PhoneNumber.is_active == True).first()
    
    if not phone_record:
        logger.warning(f"⚠️ Received message to unassigned number: {clean_to}")
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    business_user = phone_record.owner

    # 3. Identify the Lead (Who is sending the message?)
    # We look for an existing lead belonging to this business with this phone number
    lead_record = db.query(Lead).filter(
        Lead.owner_id == business_user.id,
        Lead.phone_number.like(f"%{clean_from[-9:]}%") # Match last 9 digits to avoid country code prefix issues
    ).first()

    lead_name = lead_record.name if lead_record else "Guest"

    # 4. Construct the AI Persona/System Prompt based on Business Settings
    biz_name = business_user.business_name or "our business"
    biz_type = business_user.business_type or "service"
    products = business_user.products_services or "Ask how we can help."
    instructions = business_user.custom_instructions or "Be helpful and polite."
    tone = business_user.ai_tone or "Friendly"
    lang = business_user.ai_language or "he-IL"

    system_prompt = f"""
    You are an AI assistant for '{biz_name}', a {biz_type} business.
    Your tone must be: {tone}. Language: {lang}.
    
    Products/Services offered:
    {products}
    
    Specific Instructions from the business owner:
    {instructions}
    
    IMPORTANT: Never break character. Always answer on behalf of {biz_name}. Keep answers concise and suitable for WhatsApp.
    """

    # 5. Process the message through the AI Engine asynchronously
    logger.info(f"🧠 Sending message to AI Engine for business: {biz_name}")
    
    # We don't want to block the Twilio HTTP response while AI generates, 
    # but for simplicity in V1, we await it. (In production with heavy traffic, use background tasks)
    try:
        ai_response = await ai_engine.analyze_interaction(
            system_prompt=system_prompt,
            text_input=Body,
            sender_name=lead_name
        )
        
        reply_text = ai_response.get("reply_text", "מצטער, אני מתקשה להבין כרגע. אפשר לנסח מחדש?")
        
    except Exception as e:
        logger.error(f"❌ AI Processing Failed: {e}")
        reply_text = "הייתה שגיאה טכנית קטנה, נחזור אליך בהקדם."

    # 6. Send the response back via WhatsApp Adapter (bypassing Twilio's default TwiML for better control)
    # Why? Because TwiML response has a strict 15-second timeout, AI might take 3-5 seconds.
    # By using our adapter, we send it asynchronously.
    whatsapp_adapter.send_message(to_phone=clean_from, text=reply_text)

    # 7. Return empty TwiML to Twilio so they know we received the webhook successfully
    # (We already sent the actual reply via the API above)
    resp = MessagingResponse()
    return Response(content=str(resp), media_type="application/xml")