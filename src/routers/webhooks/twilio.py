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

# ... (verify_twilio_signature stays the same) ...

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
    """
    Handles incoming messages with dual logic:
    1. OWNER MODE: Voice commands for broadcasting to tagged groups.
    2. LEAD MODE: Automated AI sales chat with conversational memory.
    """
    # await verify_twilio_signature(request) # Security active
    
    clean_to = To.replace("whatsapp:", "").strip()
    clean_from = From.replace("whatsapp:", "").strip()

    # 1. Identify the Business and Owner
    phone_record = db.query(PhoneNumber).filter(PhoneNumber.number == clean_to, PhoneNumber.is_active == True).first()
    if not phone_record:
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    owner = phone_record.owner

    # ------------------------------------------------------------------
    # 👑 PHASE A: OWNER COMMAND MODE (Voice-to-Action)
    # ------------------------------------------------------------------
    if clean_from == owner.personal_whatsapp:
        logger.info(f"👑 Owner Command detected from {clean_from}")
        
        command_text = Body
        
        # Handle Voice Note from Owner
        if NumMedia > 0 and "audio" in (MediaContentType0 or ""):
            logger.info("🎙️ Processing Owner Voice Command via Whisper...")
            command_text = await whisper_service.transcribe_from_url(MediaUrl0)
            logger.info(f"📝 Transcribed Command: {command_text}")

        # Use Gemini to parse the command intent
        available_tags = [t.name for t in owner.tags]
        parse_prompt = f"""
        You are the System Controller for '{owner.business_name}'.
        The owner sent a command: "{command_text}"
        
        Available Customer Tags: {available_tags}
        
        Task:
        1. Is this a broadcast request? (True/False)
        2. Which TAG is the target? (Must match one from the list or 'all')
        3. What is the MESSAGE to be sent? (Keep it exactly as the owner intended).
        
        Return JSON only: {{"is_broadcast": bool, "target_tag": str, "message": str}}
        """
        
        intent = await ai_engine.analyze_interaction(system_prompt=parse_prompt, text_input=command_text)
        
        if intent.get("is_broadcast") and intent.get("message"):
            target_tag_name = intent.get("target_tag")
            broadcast_msg = intent.get("message")
            
            # Find leads matching the tag
            query = db.query(Lead).filter(Lead.user_id == owner.id)
            if target_tag_name != 'all':
                query = query.join(Lead.tags).filter(Tag.name == target_tag_name)
            
            target_leads = query.all()
            
            # Execute Broadcast
            for lead in target_leads:
                whatsapp_adapter.send_message(to_phone=lead.phone_number, text=broadcast_msg)
                db.add(Message(lead_id=lead.id, sender_type="bot", content=broadcast_msg))
            
            db.commit()
            
            # Notify owner of success
            confirm_msg = f"✅ בוצע! ההודעה נשלחה ל-{len(target_leads)} לקוחות בקבוצת '{target_tag_name}'."
            whatsapp_adapter.send_message(to_phone=owner.personal_whatsapp, text=confirm_msg)
            return Response(content=str(MessagingResponse()), media_type="application/xml")

    # ------------------------------------------------------------------
    # 👤 PHASE B: REGULAR LEAD INTERACTION
    # ------------------------------------------------------------------
    # Identify or Create Lead
    lead_record = db.query(Lead).filter(
        Lead.user_id == owner.id,
        Lead.phone_number.like(f"%{clean_from[-9:]}%")
    ).first()

    if not lead_record:
        lead_record = Lead(user_id=owner.id, name="New Lead", phone_number=clean_from, source=LeadSource.WHATSAPP)
        db.add(lead_record)
        db.commit()
        db.refresh(lead_record)

    # Save to history
    db.add(Message(lead_id=lead_record.id, sender_type="user", content=Body))
    db.commit()

    # If muted for human handoff, stop here
    if not lead_record.bot_active:
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    # Fetch History for Memory
    history = db.query(Message).filter(Message.lead_id == lead_record.id).order_by(Message.created_at.desc()).limit(10).all()
    history.reverse()
    history_context = "\n".join([f"{'Customer' if m.sender_type=='user' else 'AI'}: {m.content}" for m in history])

    system_prompt = f"""
    You are the Virtual Secretary for '{owner.business_name}'. 
    Context: {owner.business_profile.products_services}
    Instructions: {owner.business_profile.custom_instructions}
    
    Rules:
    - Answer based on chat history.
    - If user asks for human/manager, start reply with [HANDOFF].
    
    History:
    {history_context}
    """

    try:
        ai_response = await ai_engine.analyze_interaction(system_prompt=system_prompt, text_input=Body)
        reply_text = ai_response.get("reply_text", "מצטער, חלה שגיאה.")
    except Exception as e:
        logger.error(f"AI Fail: {e}")
        reply_text = "סליחה, אני זמינה שוב בעוד רגע."

    # Process Handoff
    if "[HANDOFF]" in reply_text:
        reply_text = reply_text.replace("[HANDOFF]", "").strip()
        lead_record.bot_active = False
        lead_record.requires_human = True

    # Save AI response and send
    db.add(Message(lead_id=lead_record.id, sender_type="bot", content=reply_text))
    db.commit()
    whatsapp_adapter.send_message(to_phone=clean_from, text=reply_text)

    return Response(content=str(MessagingResponse()), media_type="application/xml")