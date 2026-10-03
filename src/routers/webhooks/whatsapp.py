# src/routers/webhooks/whatsapp.py
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.config import settings
from src.database.models import (
    AIAgent,
    Lead,
    LeadSource,
    LeadStatus,
    Message,
    PhoneNumber,
    PlanTier,
    User,
    WebhookDLQ,
    WebhookProvider,
)
from src.database.session import SessionLocal

router = APIRouter(tags=["Webhooks - WhatsApp"])
logger = logging.getLogger("WhatsAppWebhook")

STARTER_MESSAGE_LIMIT = 10
PRO_MESSAGE_LIMIT = 2000

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _is_production() -> bool:
    return (settings.APP_ENV or "").lower() == "production"

def _digits_only(value: Optional[str]) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())

async def verify_whatsapp_signature(request: Request) -> None:
    """Validates X-Hub-Signature-256 against WHATSAPP_APP_SECRET."""
    secret = (getattr(settings, "WHATSAPP_APP_SECRET", None) or "").strip()
    signature = request.headers.get("X-Hub-Signature-256") or request.headers.get("x-hub-signature-256")
    client_host = request.client.host if request.client else "unknown"

    if not secret:
        if _is_production():
            logger.error("WHATSAPP_APP_SECRET is not configured; rejecting Meta POST.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WhatsApp signature secret is not configured",
            )
        logger.warning("WHATSAPP_APP_SECRET unset in %s; skipping signature check.", settings.APP_ENV)
        return

    if not signature or not signature.startswith("sha256="):
        logger.warning("Missing or malformed X-Hub-Signature-256 from %s", client_host)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature missing")

    body = await request.body()
    expected_hash = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    received_hash = signature.split("=", 1)[1].strip().lower()

    if len(received_hash) != len(expected_hash) or not hmac.compare_digest(received_hash, expected_hash):
        logger.error("SECURITY ALERT: Invalid WhatsApp signature from %s", client_host)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

@router.get("")
@router.get("/")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge"),
):
    """Meta (Facebook) Verification Handshake."""
    verify_token = settings.WHATSAPP_VERIFY_TOKEN

    if mode == "subscribe" and token == verify_token:
        logger.info("WhatsApp webhook verified successfully.")
        return PlainTextResponse(content=challenge)

    logger.warning("WhatsApp verification failed: invalid token.")
    raise HTTPException(status_code=403, detail="Verification failed")

def _resolve_tenant(db: Session, metadata: dict) -> tuple[Optional[User], Optional[PhoneNumber]]:
    phone_number_id = (metadata.get("phone_number_id") or "").strip()
    display_phone = _digits_only(metadata.get("display_phone_number"))

    phone_record = None
    if phone_number_id:
        phone_record = db.query(PhoneNumber).filter(PhoneNumber.provider_id == phone_number_id).first()

    if phone_record is None and display_phone:
        tail = display_phone[-9:] if len(display_phone) >= 9 else display_phone
        if tail:
            phone_record = db.query(PhoneNumber).filter(PhoneNumber.number.contains(tail)).first()

    user = None
    if phone_record is not None:
        user = db.query(User).filter(User.id == phone_record.owner_id).first()
    elif display_phone:
        tail = display_phone[-9:] if len(display_phone) >= 9 else display_phone
        if tail:
            user = db.query(User).filter(User.assigned_phone_number.contains(tail)).first()
    return user, phone_record

def _tenant_graph_credentials(user: User, phone_record: Optional[PhoneNumber]) -> tuple[Optional[str], Optional[str]]:
    token = getattr(user, "whatsapp_access_token", None) or settings.META_ACCESS_TOKEN
    phone_id = (
        getattr(user, "whatsapp_phone_number_id", None)
        or (phone_record.provider_id if phone_record else None)
        or settings.WHATSAPP_PHONE_ID
    )
    return token, phone_id

def _send_tenant_message(user: User, phone_record: Optional[PhoneNumber], to_phone: str, text: str) -> bool:
    from src.services.communication.whatsapp import whatsapp_adapter
    token, phone_id = _tenant_graph_credentials(user, phone_record)
    return whatsapp_adapter.send_message(
        to_phone=to_phone,
        text=text,
        phone_number_id=phone_id,
        access_token=token,
    )

def _extract_text_body(message: dict) -> Optional[str]:
    msg_type = message.get("type")
    if msg_type == "text":
        body = (message.get("text") or {}).get("body")
        return body.strip() if isinstance(body, str) and body.strip() else None
    if msg_type == "button":
        text = (message.get("button") or {}).get("text")
        return text.strip() if isinstance(text, str) and text.strip() else None
    if msg_type == "interactive":
        interactive = message.get("interactive") or {}
        for key in ("button_reply", "list_reply"):
            title = (interactive.get(key) or {}).get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()
    return None

async def _handle_inbound_message(
    db: Session,
    metadata: dict,
    contacts: list,
    message: dict,
) -> str:
    sender_id = _digits_only(message.get("from"))
    if not sender_id:
        logger.warning("Skipping Meta message without sender id: %s", message.get("id"))
        return "ignored_incomplete_message"

    contact_profile = {}
    if contacts:
        contact_profile = (contacts[0] or {}).get("profile") or {}
    sender_name = contact_profile.get("name") or "Guest"

    user, phone_record = _resolve_tenant(db, metadata)
    bot_phone_number = metadata.get("display_phone_number")
    if not user:
        logger.warning("Received message for unassigned number: %s", bot_phone_number)
        return "ignored_unassigned_number"

    agent = db.query(AIAgent).filter(AIAgent.user_id == user.id).first()
    if not agent or not agent.is_active:
        logger.info("AI agent disabled or missing for %s", bot_phone_number)
        return "agent_disabled"

    tenant_context = {
        "user_id": user.id,
        "email": user.email,
        "plan_tier": user.plan_tier,
        "monthly_ai_messages": user.monthly_ai_messages or 0,
        "business_profile_path": user.business_profile_path,
        "system_prompt": agent.system_prompt or "",
    }

    tail_match = f"%{sender_id[-9:]}%" if len(sender_id) >= 9 else f"%{sender_id}%"
    lead_record = db.query(Lead).filter(Lead.user_id == user.id, Lead.phone_number.like(tail_match)).first()
    
    if not lead_record:
        try:
            with db.begin_nested():
                lead_record = Lead(
                    user_id=user.id,
                    name=sender_name,
                    phone_number=sender_id,
                    source=LeadSource.WHATSAPP,
                    status=LeadStatus.IN_PROGRESS,
                    needs_followup=False
                )
                db.add(lead_record)
            db.flush()
        except IntegrityError:
            db.rollback()
            lead_record = db.query(Lead).filter(Lead.user_id == user.id, Lead.phone_number.like(tail_match)).first()

    if lead_record and lead_record.status == LeadStatus.NEW:
        lead_record.status = LeadStatus.IN_PROGRESS
        lead_record.needs_followup = False
        db.flush()

    msg_type = message.get("type")
    text_body = _extract_text_body(message)

    if msg_type == "audio":
        media_id = (message.get("audio") or {}).get("id")
        logger.info("Audio message received via Meta Cloud API (media_id=%s); text RAG path skipped.", media_id)
        return "audio_received"

    if not text_body:
        logger.info("Ignoring unsupported or empty Meta message type=%s id=%s", msg_type, message.get("id"))
        return "ignored_unsupported_type"

    db.add(Message(lead_id=lead_record.id, sender_type="user", content=text_body))
    db.flush()

    if not lead_record.bot_active:
        logger.info("Muted lead %s (human takeover); message saved.", sender_id)
        return "muted"

    max_limit = PRO_MESSAGE_LIMIT if tenant_context["plan_tier"] == PlanTier.PRO else STARTER_MESSAGE_LIMIT
    if tenant_context["monthly_ai_messages"] >= max_limit:
        logger.warning("User %s exceeded AI message limit.", tenant_context["email"])
        _send_tenant_message(
            user=user,
            phone_record=phone_record,
            to_phone=sender_id,
            text="מערכת המענה האוטומטי מושבתת זמנית עקב הגעה למגבלת ההודעות החודשית."
        )
        return "limit_exceeded"

    try:
        from src.services.ai.engine import ai_engine
        from src.services.profile_loader import load_tenant_profile

        profile_data = await load_tenant_profile(tenant_context["business_profile_path"]) if tenant_context["business_profile_path"] else {}
        
        # התאמה למבנה הקיים של ai_engine
        ai_response = await ai_engine.analyze_interaction(
            system_prompt=tenant_context["system_prompt"],
            text_input=text_body,
            sender_name=sender_name
        )
        
        reply_text = ai_response.get("reply_text") or "שלום, רשמתי את פנייתך ונחזור אליך בהקדם."

        if reply_text:
            success = _send_tenant_message(user, phone_record, sender_id, reply_text)
            if success:
                db.add(Message(lead_id=lead_record.id, sender_type="bot", content=reply_text))
                user.monthly_ai_messages = (user.monthly_ai_messages or 0) + 1
                db.flush()
                return "ai_replied"
            else:
                logger.error("Failed to send WhatsApp message via adapter.")
                return "whatsapp_send_failure"
                
    except Exception as ai_err:
        logger.error("Error during AI generation or response dispatch: %s", ai_err)
        return "ai_processing_error"
        
    return "no_action"

@router.post("")
@router.post("/")
async def handle_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """The main Webhook receiver endpoint for Meta Cloud API POST requests."""
    await verify_whatsapp_signature(request)
    
    try:
        raw_body = await request.body()
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as parse_err:
        logger.error("Failed to parse incoming Webhook JSON body: %s", parse_err)
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    if payload.get("object") != "whatsapp_business_account":
        return JSONResponse(status_code=200, content={"status": "ignored_object_type"})
        
    entries = payload.get("entry") or []
    if not entries:
        return JSONResponse(status_code=200, content={"status": "empty_entries"})
        
    processing_results = []
    
    for entry in entries:
        changes = entry.get("changes") or []
        for change in changes:
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            messages = value.get("messages") or []
            contacts = value.get("contacts") or []
            
            if not messages:
                continue
                
            for message in messages:
                try:
                    with db.begin_nested():
                        result = await _handle_inbound_message(db, metadata, contacts, message)
                        processing_results.append(result)
                except Exception as msg_err:
                    logger.error("Failed processing message. Stashing event to WebhookDLQ: %s", msg_err)
                    
                    try:
                        # תיקון: שימוש בשדה הנכון 'error_reason' במקום 'error_message'
                        dlq_fallback = WebhookDLQ(
                            provider=WebhookProvider.META,
                            payload=payload,
                            error_reason=str(msg_err),
                            retry_count=0,
                            is_resolved=False
                        )
                        db.add(dlq_fallback)
                        processing_results.append("failed_logged_to_dlq")
                    except Exception as dlq_err:
                        logger.critical("DLQ Table write fatal error: %s", dlq_err)
                        processing_results.append("failed_dlq_write_error")
                    
    db.commit()
    return JSONResponse(status_code=200, content={"status": "processed", "results": processing_results})