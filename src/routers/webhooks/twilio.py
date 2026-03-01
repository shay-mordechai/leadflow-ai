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
from src.database.models import PhoneNumber, Lead, User, Message, LeadSource
from src.services.ai.engine import ai_engine
from src.services.communication.whatsapp import whatsapp_adapter

router = APIRouter(tags=["Webhooks - Twilio"])
logger = logging.getLogger("TwilioWebhook")

async def verify_twilio_signature(request: Request):
    """
    Security Middleware: Validates that the incoming request is genuinely from Twilio.
    """
    if not settings.TWILIO_AUTH_TOKEN:
        logger.warning("⚠️ Skipping Twilio Signature Verification: Auth Token Missing")
        return True

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    signature = request.headers.get("X-Twilio-Signature", "")
    
    url = str(request.url).replace("http://", "https://") if "my-leads.app" in str(request.url) else str(request.url)
    form_data = await request.form()
    
    if not validator.validate(url, dict(form_data), signature):
        logger.warning(f"❌ SECURITY ALERT: Fake Twilio Request blocked from IP: {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature"
        )
    return True

@router.post("/sms")
async def incoming_sms_message(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    To: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Handles incoming WhatsApp messages.
    Includes Conversational Memory, Auto-Lead Creation, and Human Handoff logic.
    """
    await verify_twilio_signature(request)
    logger.info(f"📩 Incoming Message | From: {From} | To: {To} | Body: {Body}")

    clean_to = To.replace("whatsapp:", "").strip()
    clean_from = From.replace("whatsapp:", "").strip()

    # 1. Identify the Business Owner
    phone_record = db.query(PhoneNumber).filter(PhoneNumber.number == clean_to, PhoneNumber.is_active == True).first()
    if not phone_record:
        logger.warning(f"⚠️ Received message to unassigned number: {clean_to}")
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    business_user = phone_record.owner

    # 2. Identify or Create the Lead
    lead_record = db.query(Lead).filter(
        Lead.user_id == business_user.id,
        Lead.phone_number.like(f"%{clean_from[-9:]}%")
    ).first()

    if not lead_record:
        logger.info(f"🆕 Creating new Lead for phone: {clean_from}")
        lead_record = Lead(
            user_id=business_user.id,
            name="New WhatsApp Lead",
            phone_number=clean_from,
            source=LeadSource.WHATSAPP
        )
        db.add(lead_record)
        db.commit()
        db.refresh(lead_record)

    # 3. Save incoming message to Conversational Memory
    new_msg = Message(lead_id=lead_record.id, sender_type="user", content=Body)
    db.add(new_msg)
    db.commit()

    # 4. Check Human Handoff Status (Is the Bot silenced?)
    if not lead_record.bot_active:
        logger.info(f"🔇 Bot is muted for Lead {lead_record.id}. Message saved to Dashboard only.")
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    # 5. Build Context & AI Persona
    biz_name = business_user.business_name or "our business"
    biz_type = business_user.business_type or "service"
    products = business_user.products_services or "Ask how we can help."
    instructions = business_user.custom_instructions or "Be helpful and polite."

    # Fetch last 10 messages for AI memory
    history = db.query(Message).filter(Message.lead_id == lead_record.id).order_by(Message.created_at.desc()).limit(10).all()
    history.reverse()
    chat_history_text = "\n".join([f"{'Customer' if m.sender_type=='user' else 'AI Agent'}: {m.content}" for m in history])

    system_prompt = f"""
    You are the Virtual AI Secretary for '{biz_name}', a {biz_type} business.
    Your job is to answer customer questions and qualify them politely.
    
    Business Info & Services: {products}
    Owner Instructions: {instructions}
    
    STRICT HANDOFF RULES:
    If the customer is angry, asks a very complex question you can't answer, or explicitly asks to speak to a human/manager, you MUST stop the automated chat.
    To handoff, your response MUST begin with exactly this keyword: "[HANDOFF]".
    Example: "[HANDOFF] הבנתי, אני מעבירה את השיחה לצוות האנושי שלנו שיחזור אליך בהקדם."
    
    Recent Chat History:
    {chat_history_text}
    """

    # 6. Get AI Response
    try:
        ai_response = await ai_engine.analyze_interaction(
            system_prompt=system_prompt,
            text_input=Body,
            sender_name=lead_record.name or "Customer"
        )
        reply_text = ai_response.get("reply_text", "מצטער, אני מתקשה להבין. אפשר לנסח מחדש?")
    except Exception as e:
        logger.error(f"❌ AI Processing Failed: {e}")
        reply_text = "מערכת ההודעות שלנו בבדיקה כרגע, נחזור אליך בקרוב."

    # 7. Process Handoff Keyword
    if "[HANDOFF]" in reply_text:
        reply_text = reply_text.replace("[HANDOFF]", "").strip()
        lead_record.bot_active = False
        lead_record.requires_human = True
        logger.info(f"🛑 Human Handoff triggered for Lead {lead_record.id}. Bot muted.")

    # 8. Save AI Reply to Memory
    ai_msg = Message(lead_id=lead_record.id, sender_type="bot", content=reply_text)
    db.add(ai_msg)
    db.commit()

    # 9. Send via WhatsApp
    whatsapp_adapter.send_message(to_phone=clean_from, text=reply_text)

    return Response(content=str(MessagingResponse()), media_type="application/xml")