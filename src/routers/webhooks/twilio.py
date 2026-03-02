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
    print(f"\n[TWILIO WEBHOOK] Received message from {From} to {To}: {Body}")
    clean_to = To.replace("whatsapp:", "").strip()
    clean_from = From.replace("whatsapp:", "").strip()

    # 1. Identify the Business and Owner
    phone_record = db.query(PhoneNumber).filter(PhoneNumber.number == clean_to, PhoneNumber.is_active == True).first()
    
    if not phone_record:
        print(f"[TWILIO WEBHOOK] ⚠️ Destination number {clean_to} not found in database.")
        # --- QA TESTING FALLBACK ---
        if clean_to == "+97233829709":
            print("[TWILIO WEBHOOK] 🔧 QA MODE: Routing test number to the newest registered user.")
            owner = db.query(User).order_by(User.created_at.desc()).first()
            if not owner:
                return Response(content=str(MessagingResponse()), media_type="application/xml")
        else:
            return Response(content=str(MessagingResponse()), media_type="application/xml")
    else:
        owner = phone_record.owner

    # ------------------------------------------------------------------
    # 👑 PHASE A: OWNER COMMAND MODE (Voice-to-Action)
    # ------------------------------------------------------------------
    if clean_from == owner.personal_whatsapp:
        print(f"[TWILIO WEBHOOK] 👑 Owner Command detected from {clean_from}")
        command_text = Body
        
        if NumMedia > 0 and "audio" in (MediaContentType0 or ""):
            command_text = await whisper_service.transcribe_from_url(MediaUrl0)
            print(f"[TWILIO WEBHOOK] 📝 Transcribed Command: {command_text}")

        available_tags = [t.name for t in owner.tags]
        parse_prompt = f"""
        You are the System Controller for '{owner.business_name}'.
        The owner sent a command: "{command_text}"
        Available Customer Tags: {available_tags}
        Task:
        1. Is this a broadcast request?
        2. Which TAG is the target? (Must match one from the list or 'all')
        3. What is the MESSAGE to be sent?
        """
        
        owner_schema = """{
            "is_broadcast": boolean, 
            "target_tag": "string", 
            "message": "string"
        }"""
        
        intent = await ai_engine.analyze_interaction(system_prompt=parse_prompt, text_input=command_text, expected_schema=owner_schema)
        
        if intent.get("is_broadcast") and intent.get("message"):
            target_tag_name = intent.get("target_tag")
            broadcast_msg = intent.get("message")
            
            query = db.query(Lead).filter(Lead.user_id == owner.id)
            if target_tag_name != 'all':
                query = query.join(Lead.tags).filter(Tag.name == target_tag_name)
            
            target_leads = query.all()
            
            for lead in target_leads:
                whatsapp_adapter.send_message(to_phone=lead.phone_number, text=broadcast_msg)
                db.add(Message(lead_id=lead.id, sender_type="bot", content=broadcast_msg))
            
            db.commit()
            confirm_msg = f"✅ בוצע! ההודעה נשלחה ל-{len(target_leads)} לקוחות בקבוצת '{target_tag_name}'."
            whatsapp_adapter.send_message(to_phone=owner.personal_whatsapp, text=confirm_msg)
            return Response(content=str(MessagingResponse()), media_type="application/xml")

    # ------------------------------------------------------------------
    # 👤 PHASE B: REGULAR LEAD INTERACTION
    # ------------------------------------------------------------------
    print(f"[TWILIO WEBHOOK] 👤 Processing Lead Message from {clean_from}")
    
    lead_record = db.query(Lead).filter(
        Lead.user_id == owner.id,
        Lead.phone_number.like(f"%{clean_from[-9:]}%")
    ).first()

    if not lead_record:
        lead_record = Lead(user_id=owner.id, name="New Lead", phone_number=clean_from, source=LeadSource.WHATSAPP)
        db.add(lead_record)
        db.commit()
        db.refresh(lead_record)

    db.add(Message(lead_id=lead_record.id, sender_type="user", content=Body))
    db.commit()

    if not lead_record.bot_active:
        print(f"[TWILIO WEBHOOK] 🔇 Bot is MUTED for {clean_from}. Ignoring message.")
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    history = db.query(Message).filter(Message.lead_id == lead_record.id).order_by(Message.created_at.desc()).limit(10).all()
    history.reverse()
    history_context = "\n".join([f"{'Customer' if m.sender_type=='user' else 'AI'}: {m.content}" for m in history])

    biz_context = owner.business_profile.products_services if owner.business_profile else "General Business Operations"
    biz_instructions = owner.business_profile.custom_instructions if owner.business_profile else "Provide helpful and polite responses."

    system_prompt = f"""
    You are the Virtual Secretary for '{owner.business_name}'. 
    Context: {biz_context}
    Instructions: {biz_instructions}
    
    Rules:
    - Answer based on chat history.
    - If user asks for a human, representative, or manager, you MUST set needs_human_escalation to true.
    
    History:
    {history_context}
    """

    # Safety initialization
    ai_response = {}
    reply_text = "סליחה, אני זמינה שוב בעוד רגע."

    try:
        ai_response = await ai_engine.analyze_interaction(system_prompt=system_prompt, text_input=Body)
        reply_text = ai_response.get("reply_text", "מצטער, חלה שגיאה.")
    except Exception as e:
        print(f"[TWILIO WEBHOOK] ❌ AI Generation Failed: {e}")

    # 🛟 SAFETY NET: Hardcoded Handoff Keywords (Bypasses AI if it fails/ignores)
    handoff_keywords = ["human", "representative", "manager", "נציג", "אנושי", "מנהל", "שירות לקוחות"]
    needs_human_ai = ai_response.get("needs_human_escalation", False)
    needs_human_fallback = any(word in Body.lower() for word in handoff_keywords)

    if needs_human_ai or needs_human_fallback or "[HANDOFF]" in reply_text:
        print(f"[TWILIO WEBHOOK] 🚨 HANDOFF TRIGGERED! AI thought: {needs_human_ai}, Fallback thought: {needs_human_fallback}")
        reply_text = reply_text.replace("[HANDOFF]", "").strip()
        
        # Mute the bot
        lead_record.bot_active = False
        lead_record.requires_human = True
        
        # Optional: Change reply text to confirm handoff if it's still default
        if "שגיאה" in reply_text or "רגע" in reply_text:
            reply_text = "מיד אעביר אותך לנציג אנושי, תודה על הסבלנות."

    db.add(Message(lead_id=lead_record.id, sender_type="bot", content=reply_text))
    db.commit()
    
    whatsapp_adapter.send_message(to_phone=clean_from, text=reply_text)
    print(f"[TWILIO WEBHOOK] ✅ Successfully replied to {clean_from}")

    return Response(content=str(MessagingResponse()), media_type="application/xml")