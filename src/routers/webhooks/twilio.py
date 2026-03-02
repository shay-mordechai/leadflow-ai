# src/routers/webhooks/twilio.py
import logging
import asyncio
from fastapi import APIRouter, Request, Form, Response, HTTPException, status, Depends
from sqlalchemy.orm import Session
from twilio.twiml.messaging_response import MessagingResponse

# Internal imports
from src.config import settings
from src.database.session import get_db
from src.database.models import PhoneNumber, Lead, User, Message, LeadSource, Tag
from src.services.ai.engine import ai_engine
# Assuming you have a whisper service for local transcription
from src.services.ai.whisper import whisper_service 
from src.services.communication.whatsapp import whatsapp_adapter

router = APIRouter(tags=["Webhooks - Twilio"])
logger = logging.getLogger("TwilioWebhook")

@router.post("/sms")
async def incoming_sms_message(
    request: Request,
    From: str = Form(...),
    Body: str = Form(""),
    To: str = Form(...),
    NumMedia: int = Form(0),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
    db: Session = Depends(get_db)
):
    print(f"\n[TWILIO WEBHOOK] Incoming message from {From} to {To}: {Body}")
    clean_to = To.replace("whatsapp:", "").strip()
    clean_from = From.replace("whatsapp:", "").strip()

    # 1. Identify the Business and Owner
    phone_record = db.query(PhoneNumber).filter(PhoneNumber.number == clean_to, PhoneNumber.is_active == True).first()
    
    if not phone_record:
        # --- QA TESTING FALLBACK: Route test number to the newest user ---
        if clean_to == "+97233829709":
            owner = db.query(User).order_by(User.created_at.desc()).first()
            if not owner:
                return Response(content=str(MessagingResponse()), media_type="application/xml")
        else:
            logger.warning(f"Destination {clean_to} not found in DB.")
            return Response(content=str(MessagingResponse()), media_type="application/xml")
    else:
        owner = phone_record.owner

    # ------------------------------------------------------------------
    # 👑 PHASE A: OWNER COMMAND MODE (Broadcasting)
    # ------------------------------------------------------------------
    if clean_from == owner.personal_whatsapp:
        logger.info(f"👑 Owner Command detected from {clean_from}")
        command_text = Body
        
        if NumMedia > 0 and "audio" in (MediaContentType0 or ""):
            command_text = await whisper_service.transcribe_from_url(MediaUrl0)

        available_tags = [t.name for t in owner.tags]
        owner_prompt = f"""
        You are the System Controller for '{owner.business_name}'.
        Owner Command: "{command_text}"
        Tags: {available_tags}
        Task: Parse if this is a broadcast and return JSON only.
        """
        
        owner_schema = '{"is_broadcast": boolean, "target_tag": "string", "message": "string"}'
        intent = await ai_engine.analyze_interaction(system_prompt=owner_prompt, text_input=command_text, expected_schema=owner_schema)
        
        if intent.get("is_broadcast") and intent.get("message"):
            target_tag = intent.get("target_tag")
            query = db.query(Lead).filter(Lead.user_id == owner.id)
            if target_tag != 'all':
                query = query.join(Lead.tags).filter(Tag.name == target_tag)
            
            leads_to_msg = query.all()
            for l in leads_to_msg:
                whatsapp_adapter.send_message(to_phone=l.phone_number, text=intent.get("message"))
                db.add(Message(lead_id=l.id, sender_type="bot", content=intent.get("message")))
            
            db.commit()
            whatsapp_adapter.send_message(to_phone=owner.personal_whatsapp, text=f"✅ Sent to {len(leads_to_msg)} clients in '{target_tag}'.")
            return Response(content=str(MessagingResponse()), media_type="application/xml")

    # ------------------------------------------------------------------
    # 👤 PHASE B: SALES BRAIN - LEAD INTERACTION
    # ------------------------------------------------------------------
    lead_record = db.query(Lead).filter(
        Lead.user_id == owner.id,
        Lead.phone_number.like(f"%{clean_from[-9:]}%")
    ).first()

    if not lead_record:
        lead_record = Lead(user_id=owner.id, name="New Lead", phone_number=clean_from, source=LeadSource.WHATSAPP)
        db.add(lead_record); db.commit(); db.refresh(lead_record)

    # Save user message
    db.add(Message(lead_id=lead_record.id, sender_type="user", content=Body))
    db.commit()

    if not lead_record.bot_active:
        logger.info(f"Muted lead {clean_from} - skipping AI.")
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    # Conversational Memory (Last 10 messages)
    history = db.query(Message).filter(Message.lead_id == lead_record.id).order_by(Message.created_at.desc()).limit(10).all()
    history.reverse()
    history_str = "\n".join([f"{'Customer' if m.sender_type=='user' else 'AI'}: {m.content}" for m in history])

    # Sales Brain Context Construction
    biz = owner.business_profile
    system_prompt = f"""
    You are 'Liron', the expert sales assistant for '{owner.business_name}'.
    Goal: Assist the customer, represent the brand, and drive sales/bookings.
    
    Business Knowledge: {biz.products_services if biz else 'Professional service provider'}
    Tone/Style: {biz.ai_tone if biz else 'Professional and friendly'}
    Owner Notes: {biz.custom_instructions if biz else 'Answer questions helpfully.'}
    
    Context History:
    {history_str}
    
    IMPORTANT RULES:
    1. If the user asks for a real person, human, manager, or representative, set 'needs_human_escalation' to true.
    2. Be concise and speak ONLY in Hebrew.
    """

    try:
        ai_res = await ai_engine.analyze_interaction(system_prompt=system_prompt, text_input=Body, sender_name=lead_record.name)
        reply_text = ai_res.get("reply_text", "תודה על ההודעה, נציג יחזור אליך בהקדם.")
    except Exception as e:
        logger.error(f"AI Engine failure: {e}")
        reply_text = "תודה, נציג אנושי יצור איתך קשר בדקות הקרובות."
        ai_res = {"needs_human_escalation": True}

    # Handoff Safety Net: AI Flag OR Keyword match
    handoff_keys = ["נציג", "אנושי", "מנהל", "human", "representative", "manager"]
    if ai_res.get("needs_human_escalation") or any(k in Body.lower() for k in handoff_keys):
        logger.info(f"🚨 Handoff triggered for {clean_from}")
        lead_record.bot_active = False
        lead_record.requires_human = True
        db.commit()

    # Save bot response and send
    db.add(Message(lead_id=lead_record.id, sender_type="bot", content=reply_text))
    db.commit()
    whatsapp_adapter.send_message(to_phone=clean_from, text=reply_text)

    return Response(content=str(MessagingResponse()), media_type="application/xml")