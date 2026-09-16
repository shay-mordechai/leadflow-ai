# src/routers/webhooks/whatsapp.py
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from src.config import settings
from src.database.models import AIAgent, Lead, LeadSource, LeadStatus, Message, PhoneNumber, PlanTier, User
from src.database.session import SessionLocal
from src.services.ai.engine import ai_engine
from src.services.communication.whatsapp import whatsapp_adapter
from src.services.profile_loader import load_tenant_profile

router = APIRouter(tags=["Webhooks - WhatsApp"])
logger = logging.getLogger("WhatsAppWebhook")

STARTER_MESSAGE_LIMIT = 10
PRO_MESSAGE_LIMIT = 2000


def _is_production() -> bool:
    return (settings.APP_ENV or "").lower() == "production"


def _digits_only(value: Optional[str]) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


async def verify_whatsapp_signature(request: Request) -> None:
    """
    Validates X-Hub-Signature-256 against WHATSAPP_APP_SECRET.
    Production always requires a valid signature. Development may skip only
    when the app secret has not been configured yet.
    """
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
        await request.body()
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
            phone_record = (
                db.query(PhoneNumber)
                .filter(PhoneNumber.number.contains(tail))
                .first()
            )

    user = None
    if phone_record is not None:
        user = db.query(User).filter(User.id == phone_record.owner_id).first()
    elif display_phone:
        tail = display_phone[-9:] if len(display_phone) >= 9 else display_phone
        if tail:
            user = (
                db.query(User)
                .filter(User.assigned_phone_number.contains(tail))
                .first()
            )
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

    # Cache detached-safe primitives before later commits.
    tenant_context = {
        "user_id": user.id,
        "email": user.email,
        "plan_tier": user.plan_tier,
        "monthly_ai_messages": user.monthly_ai_messages or 0,
        "business_profile_path": user.business_profile_path,
        "system_prompt": agent.system_prompt or "",
    }

    lead_record = (
        db.query(Lead)
        .filter(
            Lead.user_id == user.id,
            Lead.phone_number.like(f"%{sender_id[-9:]}%"),
        )
        .first()
    )
    if not lead_record:
        lead_record = Lead(
            user_id=user.id,
            name=sender_name,
            phone_number=sender_id,
            source=LeadSource.WHATSAPP,
        )
        db.add(lead_record)
        db.commit()
        db.refresh(lead_record)

    if lead_record.status == LeadStatus.NEW:
        lead_record.status = LeadStatus.IN_PROGRESS
        lead_record.needs_followup = False
        db.commit()

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
    db.commit()

    if not lead_record.bot_active:
        logger.info("Muted lead %s (human takeover); message saved.", sender_id)
        return "muted"

    max_limit = PRO_MESSAGE_LIMIT if tenant_context["plan_tier"] == PlanTier.PRO else STARTER_MESSAGE_LIMIT
    if tenant_context["monthly_ai_messages"] >= max_limit:
        logger.warning("User %s exceeded AI message limit.", tenant_context["email"])
        _send_tenant_message(
            user,
            phone_record,
            sender_id,
            "We apologize, but this automated assistant is temporarily unavailable. A human representative will contact you soon.",
        )
        return "limit_exceeded"

    profile_data = await load_tenant_profile(tenant_context["business_profile_path"])
    services_str = json.dumps(profile_data.get("services", []), ensure_ascii=False)
    faqs_str = json.dumps(profile_data.get("faqs", []), ensure_ascii=False)
    funnel_str = json.dumps(profile_data.get("qualification_funnel", {}), ensure_ascii=False)

    business_rag_context = (
        "\n\n[BUSINESS IDENTITY & CATALOG]\n"
        f"Business Name: {profile_data.get('business_name', 'Business')}\n"
        f"Business Type: {profile_data.get('business_type', 'Service')}\n"
        f"Brand Tone: {profile_data.get('tone', 'polite, helpful and concise')}\n"
        f"Currency: {profile_data.get('currency', 'ILS')}\n"
        f"Available Services: {services_str}\n"
        f"FAQs & Policies: {faqs_str}\n"
        f"Qualification Funnel Strategy: {funnel_str}\n\n"
        "[CORE GUARDRAILS & PRIVACY]\n"
        "1. Strict Identity: Represent ONLY this business. Do not hallucinate external services or invent unlisted prices.\n"
        "2. Human Escalation: If the lead requests human support or an inquiry falls outside the catalog, state politely that a representative will follow up.\n"
        "3. Privacy & Compliance: Data is subject to a strict 24-hour retention cycle. Never ask for passwords, credit card numbers, or government IDs."
    )

    israel_tz = ZoneInfo("Asia/Jerusalem")
    current_time_il = datetime.now(israel_tz).strftime("%A, %Y-%m-%d %H:%M:%S")
    time_aware_system_prompt = (
        f"{tenant_context['system_prompt']}{business_rag_context}\n\n"
        f"[SYSTEM CLOCK]\nThe current Date and Time in Israel is: {current_time_il}"
    )

    ai_response = await ai_engine.analyze_interaction(
        system_prompt=time_aware_system_prompt,
        text_input=text_body,
        sender_name=sender_name,
    )
    reply_text = ai_response.get("reply_text") or "I'm sorry, I encountered an error processing your request."

    user.monthly_ai_messages = tenant_context["monthly_ai_messages"] + 1
    db.commit()

    handoff_keys = ["נציג", "אנושי", "מנהל", "human", "representative", "manager"]
    lowered = text_body.lower()
    if ai_response.get("needs_human_escalation") or any(k in lowered for k in handoff_keys):
        logger.info("Handoff triggered for %s", sender_id)
        lead_record.bot_active = False
        lead_record.requires_human = True
        db.commit()

    db.add(Message(lead_id=lead_record.id, sender_type="bot", content=reply_text))
    db.commit()
    _send_tenant_message(user, phone_record, sender_id, reply_text)
    return "processed"


@router.post("")
@router.post("/")
async def whatsapp_event_listener(
    request: Request,
    _: None = Depends(verify_whatsapp_signature),
):
    """
    Receives signed Meta WhatsApp Cloud API events and runs tenant RAG replies.
    """
    db: Optional[Session] = None
    try:
        try:
            data = await request.json()
        except Exception:
            logger.warning("Meta webhook POST body was not valid JSON.")
            return {"status": "ignored_invalid_json"}

        if not isinstance(data, dict):
            return {"status": "ignored_invalid_payload"}

        entries = data.get("entry") or []
        if not entries:
            return {"status": "no_entry"}

        db = SessionLocal()
        last_status = "received"

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for change in entry.get("changes") or []:
                if not isinstance(change, dict):
                    continue
                value = change.get("value") or {}
                if not isinstance(value, dict):
                    continue

                metadata = value.get("metadata") or {}
                contacts = value.get("contacts") or []
                messages = value.get("messages") or []

                if not messages:
                    if value.get("statuses"):
                        last_status = "status_ack"
                    continue

                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    last_status = await _handle_inbound_message(db, metadata, contacts, message)

        return {"status": last_status}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("WhatsApp webhook processing error: %s", exc)
        return {"status": "error"}
    finally:
        if db is not None:
            db.close()
