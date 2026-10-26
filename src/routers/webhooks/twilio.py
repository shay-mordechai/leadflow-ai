# src/routers/webhooks/twilio.py
import base64
import hashlib
import hmac
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from twilio.twiml.messaging_response import MessagingResponse

# Internal imports
from src.config import settings
from src.database.models import Lead, LeadSource, Message, PhoneNumber, Tag, User
from src.database.session import get_db
from src.services.ai.engine import ai_engine
from src.services.ai.whisper import whisper_service
from src.services.communication.whatsapp import whatsapp_adapter
from src.tasks.audio_tasks import process_audio_message

router = APIRouter(tags=["Webhooks - Twilio"])
logger = logging.getLogger("TwilioWebhook")


# New dependency for Twilio signature validation
async def validate_twilio_signature(request: Request):
    if not settings.TWILIO_AUTH_TOKEN:
        logger.warning("TWILIO_AUTH_TOKEN is not configured. Skipping signature validation.")
        return True  # Or raise HTTPException if validation is mandatory even without token

    twilio_signature = request.headers.get("X-Twilio-Signature")
    if not twilio_signature:
        logger.warning("X-Twilio-Signature header missing.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Twilio Signature Required"
        )

    # Reconstruct the URL Twilio sent to this endpoint
    # Twilio includes the full URL, including query parameters, in the signature calculation.
    # We need to get the URL exactly as Twilio sees it.
    url = str(request.url)
    if request.query_params:
        # Twilio orders query parameters alphabetically before signing
        query_string = urlencode(sorted(request.query_params.items()))
        url = f"{str(request.base_url).rstrip('/')}{request.scope['path']}?{query_string}"
    else:
        url = f"{str(request.base_url).rstrip('/')}{request.scope['path']}"

    # Reconstruct the POST parameters Twilio sent
    # Twilio orders POST parameters alphabetically by key.
    form_params = await request.form()
    # Concatenate URL and sorted POST parameters to form the message
    message = url.encode("utf-8")
    for key in sorted(form_params.keys()):
        message += form_params[key].encode("utf-8")

    # Calculate HMAC-SHA1 signature
    auth_token = settings.TWILIO_AUTH_TOKEN.encode("utf-8")
    digest = hmac.new(auth_token, message, hashlib.sha1).digest()
    expected_signature = base64.b64encode(digest).decode("utf-8")

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, twilio_signature):
        logger.warning("Invalid Twilio signature.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio Signature"
        )

    return True


@router.post("/sms", dependencies=[Depends(validate_twilio_signature)])
async def incoming_sms_message(
    request: Request,
    From: str = Form(...),
    Body: str = Form(""),
    To: str = Form(...),
    NumMedia: int = Form(0),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
    db: Session = Depends(get_db),
):
    print(f"\n[TWILIO WEBHOOK] Incoming message from {From} to {To}: {Body}")
    clean_to = To.replace("whatsapp:", "").strip()
    clean_from = From.replace("whatsapp:", "").strip()

    # 1. Identify the Business and Owner
    phone_record = (
        db.query(PhoneNumber)
        .filter(PhoneNumber.number == clean_to, PhoneNumber.is_active == True)
        .first()
    )

    if not phone_record:
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
        intent = await ai_engine.analyze_interaction(
            system_prompt=owner_prompt,
            text_input=command_text,
            expected_schema=owner_schema,
        )

        if intent.get("is_broadcast") and intent.get("message"):
            target_tag = intent.get("target_tag")
            query = db.query(Lead).filter(Lead.user_id == owner.id)
            if target_tag != "all":
                query = query.join(Lead.tags).filter(Tag.name == target_tag)

            leads_to_msg = query.all()
            for l in leads_to_msg:
                whatsapp_adapter.send_message(to_phone=l.phone_number, text=intent.get("message"))
                db.add(Message(lead_id=l.id, sender_type="bot", content=intent.get("message")))

            db.commit()
            whatsapp_adapter.send_message(
                to_phone=owner.personal_whatsapp,
                text=f"✅ Sent to {len(leads_to_msg)} clients in '{target_tag}'.",
            )
            return Response(content=str(MessagingResponse()), media_type="application/xml")

    # ------------------------------------------------------------------
    # 👤 PHASE B: SALES BRAIN - LEAD INTERACTION
    # ------------------------------------------------------------------

    # 1. Lead Resolution
    lead_record = (
        db.query(Lead)
        .filter(Lead.user_id == owner.id, Lead.phone_number.like(f"%{clean_from[-9:]}%"))
        .first()
    )

    if not lead_record:
        lead_record = Lead(
            user_id=owner.id,
            name="New Lead",
            phone_number=clean_from,
            source=LeadSource.WHATSAPP,
        )
        db.add(lead_record)
        db.commit()
        db.refresh(lead_record)

    # 2. AUDIO ROUTING (ASYNC CELERY QUEUE)
    if NumMedia > 0 and "audio" in (MediaContentType0 or ""):
        logger.info("🎧 Customer Audio Detected. Offloading to Celery Worker.")
        # Audio tasks have their own bot_active check and save their transcriptions natively.
        process_audio_message.delay(
            media_url=MediaUrl0, sender_id=clean_from, bot_phone_number=clean_to
        )
        whatsapp_adapter.send_message(to_phone=clean_from, text="מקשיב להודעה הקולית שלך... 🎧")
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    # 3. TEXT ROUTING (STANDARD SYNC PROCESSING)
    # FIX: Save user text message FIRST so human takeover mode sees the history!
    db.add(Message(lead_id=lead_record.id, sender_type="user", content=Body))
    db.commit()

    # FIX: Human Takeover Check - Moved AFTER saving the user message to DB
    if not lead_record.bot_active:
        logger.info(
            f"🛑 Muted lead {clean_from} (Human Takeover) - User message saved, skipping AI."
        )
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    # Conversational Memory (Last 10 messages)
    history = (
        db.query(Message)
        .filter(Message.lead_id == lead_record.id)
        .order_by(Message.created_at.desc())
        .limit(10)
        .all()
    )
    history.reverse()
    history_str = "\n".join(
        [f"{'Customer' if m.sender_type == 'user' else 'AI'}: {m.content}" for m in history]
    )

    # Sales Brain Context Construction
    from src.services.ai.prompt_builder import PromptBuilder
    biz = owner.business_profile
    custom_inst = f"{biz.custom_instructions if biz else ''}\nContext History:\n{history_str}".strip()
    system_instruction = PromptBuilder.build_system_instruction(
        business_type=biz.business_type if biz else owner.business_type or "General",
        business_name=owner.business_name or "העסק שלנו",
        products_services=biz.products_services if biz else None,
        custom_instructions=custom_inst,
    )

    try:
        ai_res = await ai_engine.analyze_interaction(
            system_instruction=system_instruction, text_input=Body, sender_name=lead_record.name
        )
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
