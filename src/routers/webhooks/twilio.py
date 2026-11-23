import base64
import hashlib
import hmac
import logging
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from twilio.twiml.messaging_response import MessagingResponse

from src.config import settings
from src.database.models import Lead, LeadSource, Message, PhoneNumber, Tag, User
from src.database.session import (
    get_db,
    reset_current_tenant_context,
    set_current_tenant_context,
)
from src.security.pii import mask_body, mask_phone
from src.services.ai.engine import ai_engine
from src.services.ai.prompt_builder import PromptBuilder
from src.services.ai.whisper import whisper_service
from src.services.communication.whatsapp import whatsapp_adapter
from src.tasks.audio_tasks import process_audio_message

router = APIRouter(tags=["Webhooks - Twilio"])
logger = logging.getLogger("TwilioWebhook")

HANDOFF_KEYWORDS = ("נציג", "אנושי", "מנהל", "human", "representative", "manager")


def _normalize_phone(raw_phone: str) -> str:
    """Strip WhatsApp prefix and normalize phone formatting."""
    cleaned = raw_phone.replace("whatsapp:", "", 1).strip()
    digits_only = re.sub(r"[^\d+]", "", cleaned)
    return digits_only or cleaned


def _reconstruct_twilio_signature_url(request: Request) -> str:
    """Reconstruct the external URL used by Twilio when computing X-Twilio-Signature."""
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",")[0].strip()

    if forwarded_proto and forwarded_host:
        base = f"{forwarded_proto}://{forwarded_host}"
    else:
        base = str(request.base_url).rstrip("/")

    path = request.url.path or request.scope.get("path", "")
    if request.query_params:
        query_string = urlencode(sorted(request.query_params.items()))
        return f"{base}{path}?{query_string}"
    return f"{base}{path}"


def _empty_twiml_response() -> Response:
    """Return an empty valid TwiML response."""
    return Response(content=str(MessagingResponse()), media_type="application/xml")


async def validate_twilio_signature(request: Request) -> bool:
    """Validate incoming Twilio webhook signatures using HMAC-SHA1 and constant-time comparison."""
    if not settings.TWILIO_AUTH_TOKEN:
        logger.warning("TWILIO_AUTH_TOKEN is not configured; skipping Twilio signature validation.")
        return True

    twilio_signature = request.headers.get("X-Twilio-Signature")
    if not twilio_signature:
        logger.warning("Missing X-Twilio-Signature header on Twilio webhook request.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Twilio Signature Required",
        )

    signature_url = _reconstruct_twilio_signature_url(request)
    form_params = await request.form()

    payload = bytearray(signature_url.encode("utf-8"))
    for key in sorted(form_params.keys()):
        val = form_params[key]
        val_str = val if isinstance(val, str) else ""
        payload.extend(val_str.encode("utf-8"))

    digest = hmac.new(
        settings.TWILIO_AUTH_TOKEN.encode("utf-8"),
        bytes(payload),
        hashlib.sha1,
    ).digest()
    expected_signature = base64.b64encode(digest).decode("utf-8")

    if not hmac.compare_digest(expected_signature, twilio_signature):
        logger.warning("Invalid X-Twilio-Signature received.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio Signature",
        )

    return True


def _resolve_business_owner(db: Session, clean_to: str) -> User | None:
    """Resolve the business owner associated with the receiving Twilio number."""
    phone_record = (
        db.query(PhoneNumber)
        .filter(PhoneNumber.number == clean_to, PhoneNumber.is_active.is_(True))
        .first()
    )
    if phone_record:
        return phone_record.owner

    if clean_to == "+97233829709":
        return db.query(User).order_by(User.created_at.desc()).first()

    logger.warning(
        "Destination number %s is not mapped to an active business.", mask_phone(clean_to)
    )
    return None


def _resolve_or_create_lead(db: Session, owner_id: int, clean_from: str) -> Lead:
    """Find an existing lead for the tenant or create a new WhatsApp lead."""
    lead_record = (
        db.query(Lead).filter(Lead.user_id == owner_id, Lead.phone_number == clean_from).first()
    )
    if not lead_record and len(clean_from) >= 9:
        suffix = clean_from[-9:]
        lead_record = (
            db.query(Lead)
            .filter(Lead.user_id == owner_id, Lead.phone_number.endswith(suffix))
            .first()
        )

    if lead_record:
        return lead_record

    lead_record = Lead(
        user_id=owner_id,
        name="New Lead",
        phone_number=clean_from,
        source=LeadSource.WHATSAPP,
    )
    db.add(lead_record)
    db.commit()
    db.refresh(lead_record)
    return lead_record


async def _handle_owner_command(
    db: Session,
    owner: User,
    body: str,
    num_media: int,
    media_url: str | None,
    media_content_type: str | None,
) -> Response | None:
    """Handle owner broadcast commands when the sender matches owner.personal_whatsapp."""
    logger.info("Owner command detected from %s", mask_phone(owner.personal_whatsapp or ""))
    command_text = body or ""

    if num_media > 0 and "audio" in (media_content_type or "").lower() and media_url:
        command_text = await whisper_service.transcribe_from_url(media_url)

    available_tags = [t.name for t in (owner.tags or [])]
    owner_prompt = (
        f"You are the System Controller for '{owner.business_name}'.\n"
        f'Owner Command: "{command_text}"\n'
        f"Tags: {available_tags}\n"
        "Task: Parse if this is a broadcast and return JSON only."
    )
    owner_schema = '{"is_broadcast": boolean, "target_tag": "string", "message": "string"}'

    intent = await ai_engine.analyze_interaction(
        system_prompt=owner_prompt,
        text_input=command_text,
        expected_schema=owner_schema,
    )

    if not (isinstance(intent, dict) and intent.get("is_broadcast") and intent.get("message")):
        return None

    target_tag = intent.get("target_tag")
    broadcast_message = str(intent["message"])

    query = db.query(Lead).filter(Lead.user_id == owner.id)
    if target_tag and target_tag != "all":
        query = query.join(Lead.tags).filter(Tag.name == target_tag)

    leads_to_msg = query.all()
    sent_count = 0
    for lead in leads_to_msg:
        try:
            whatsapp_adapter.send_message(to_phone=lead.phone_number, text=broadcast_message)
            db.add(Message(lead_id=lead.id, sender_type="bot", content=broadcast_message))
            sent_count += 1
        except Exception as exc:
            logger.warning(
                "Failed sending broadcast message to lead %s: %s",
                mask_phone(lead.phone_number),
                exc,
            )

    db.commit()

    if owner.personal_whatsapp:
        whatsapp_adapter.send_message(
            to_phone=owner.personal_whatsapp,
            text=f"Sent to {sent_count} clients in '{target_tag}'.",
        )

    return _empty_twiml_response()


@router.post("/sms", dependencies=[Depends(validate_twilio_signature)])
async def incoming_sms_message(
    request: Request,
    From: str = Form(...),
    Body: str = Form(""),
    To: str = Form(...),
    NumMedia: int = Form(0),
    MediaUrl0: str | None = Form(None),
    MediaContentType0: str | None = Form(None),
    db: Session = Depends(get_db),
) -> Response:
    """Process incoming Twilio WhatsApp/SMS webhooks for owner broadcasts and lead replies."""
    logger.info(
        "[TWILIO WEBHOOK] Incoming message from %s to %s: %s",
        mask_phone(From),
        mask_phone(To),
        mask_body(Body),
    )

    clean_to = _normalize_phone(To)
    clean_from = _normalize_phone(From)

    owner = _resolve_business_owner(db, clean_to)
    if not owner:
        return _empty_twiml_response()

    tenant_token = set_current_tenant_context(str(owner.id))
    try:
        # Apply tenant RLS context to the already-open PostgreSQL transaction
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(owner.id)},
            )

        owner_phone = _normalize_phone(owner.personal_whatsapp) if owner.personal_whatsapp else ""
        if owner_phone and clean_from == owner_phone:
            broadcast_response = await _handle_owner_command(
                db=db,
                owner=owner,
                body=Body,
                num_media=NumMedia,
                media_url=MediaUrl0,
                media_content_type=MediaContentType0,
            )
            if broadcast_response is not None:
                return broadcast_response

        lead_record = _resolve_or_create_lead(db, owner.id, clean_from)

        if NumMedia > 0 and "audio" in (MediaContentType0 or "").lower():
            logger.info("Customer audio detected; offloading transcription to Celery worker.")
            process_audio_message.delay(
                media_url=MediaUrl0,
                sender_id=clean_from,
                bot_phone_number=clean_to,
            )
            whatsapp_adapter.send_message(
                to_phone=clean_from,
                text="מקשיב להודעה הקולית שלך... 🎧",
            )
            return _empty_twiml_response()

        # Persist incoming user message before checking human takeover state.
        db.add(Message(lead_id=lead_record.id, sender_type="user", content=Body))
        db.commit()

        if not lead_record.bot_active:
            logger.info(
                "Muted lead %s (human takeover active); message saved without AI reply.",
                mask_phone(clean_from),
            )
            return _empty_twiml_response()

        history = (
            db.query(Message)
            .filter(Message.lead_id == lead_record.id)
            .order_by(Message.created_at.desc())
            .limit(10)
            .all()
        )
        history.reverse()
        history_str = "\n".join(
            f"{'Customer' if m.sender_type == 'user' else 'AI'}: {m.content}" for m in history
        )

        biz = owner.business_profile
        custom_inst = (
            f"{biz.custom_instructions if biz else ''}\nContext History:\n{history_str}".strip()
        )
        system_instruction = PromptBuilder.build_system_instruction(
            business_type=biz.business_type if biz else (owner.business_type or "General"),
            business_name=owner.business_name or "העסק שלנו",
            products_services=biz.products_services if biz else None,
            custom_instructions=custom_inst,
        )

        ai_res: dict = {}
        try:
            ai_res = await ai_engine.analyze_interaction(
                system_instruction=system_instruction,
                text_input=Body,
                sender_name=lead_record.name,
            )
            reply_text = ai_res.get("reply_text") or "תודה על ההודעה, נציג יחזור אליך בהקדם."
        except Exception as exc:
            logger.error("AI engine failure for lead %s: %s", mask_phone(clean_from), exc)
            reply_text = "תודה, נציג אנושי יצור איתך קשר בדקות הקרובות."
            ai_res = {"needs_human_escalation": True}

        body_lower = (Body or "").lower()
        if ai_res.get("needs_human_escalation") or any(k in body_lower for k in HANDOFF_KEYWORDS):
            logger.info("Human handoff triggered for %s", mask_phone(clean_from))
            lead_record.bot_active = False
            lead_record.requires_human = True
            db.commit()

        db.add(Message(lead_id=lead_record.id, sender_type="bot", content=reply_text))
        db.commit()
        whatsapp_adapter.send_message(to_phone=clean_from, text=reply_text)

        return _empty_twiml_response()
    finally:
        reset_current_tenant_context(tenant_token)
