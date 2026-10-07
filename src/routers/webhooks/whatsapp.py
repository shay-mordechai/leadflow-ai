# src/routers/webhooks/whatsapp.py
import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, JSONResponse
from google import genai
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.config import settings
from src.database.models import (
    AIAgent,
    BusinessProfile,
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
from src.services.communication.whatsapp_pipeline import process_whatsapp_message
from src.services.background_task_capacity import background_task_capacity

router = APIRouter(tags=["Webhooks - WhatsApp"])
logger = logging.getLogger("WhatsAppWebhook")

STARTER_MESSAGE_LIMIT = 10
PRO_MESSAGE_LIMIT = 2000

def _is_production() -> bool:
    return (settings.APP_ENV or "").lower() == "production"


def _has_fresh_meta_timestamps(payload: dict, now: Optional[float] = None) -> bool:
    """Reject malformed or replayed Meta message/status events outside the five-minute window."""
    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        return False

    current_time = time.time() if now is None else now
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            return False
        for change in changes:
            if not isinstance(change, dict):
                return False
            value = change.get("value", {})
            if not isinstance(value, dict):
                return False
            for event_type in ("messages", "statuses"):
                events = value.get(event_type, [])
                if not isinstance(events, list):
                    return False
                for event in events:
                    if not isinstance(event, dict):
                        return False
                    timestamp = event.get("timestamp")
                    if isinstance(timestamp, bool):
                        return False
                    if isinstance(timestamp, int):
                        event_time = timestamp
                    elif isinstance(timestamp, str) and timestamp.isdecimal():
                        event_time = int(timestamp)
                    else:
                        return False

                    event_age = current_time - event_time
                    if event_age > 5 * 60 or event_age < -60:
                        return False
    return True


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

    if not hmac.compare_digest(
        received_hash.encode("utf-8"),
        expected_hash.encode("ascii"),
    ):
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
    client: genai.Client,
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

    inbound_message = Message(lead_id=lead_record.id, sender_type="user", content=text_body)
    db.add(inbound_message)
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
        from google.genai import types

        from src.schemas.ai_response import WhatsAppAgentResponse
        from src.services.ai.prompt_builder import PromptBuilder
        from src.services.profile_loader import load_tenant_profile

        profile_data = await load_tenant_profile(tenant_context["business_profile_path"]) if tenant_context["business_profile_path"] else {}
        business_profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == user.id).first()
        profile_services = profile_data.get("services", [])
        profile_faqs = profile_data.get("faqs", [])
        products_services = (
            business_profile.products_services if business_profile and business_profile.products_services
            else json.dumps({"services": profile_services, "faqs": profile_faqs}, ensure_ascii=False)
        )
        business_type = (
            business_profile.business_type if business_profile and business_profile.business_type
            else user.business_type or profile_data.get("business_type", "General")
        )
        business_name = (
            business_profile.business_name if business_profile
            else user.business_name or profile_data.get("business_name", "העסק שלנו")
        )
        custom_instructions = (
            business_profile.custom_instructions if business_profile and business_profile.custom_instructions
            else tenant_context["system_prompt"]
        )
        system_instruction = PromptBuilder.build_system_instruction(
            business_type=business_type,
            business_name=business_name,
            products_services=products_services,
            custom_instructions=custom_instructions,
        )

        previous_messages = (
            db.query(Message)
            .filter(Message.lead_id == lead_record.id, Message.id != inbound_message.id)
            .order_by(Message.created_at.desc())
            .limit(6)
            .all()
        )
        turn_prompt = PromptBuilder.build_lead_turn_prompt(
            lead_name=sender_name,
            lead_source=str(lead_record.source.value if hasattr(lead_record.source, "value") else lead_record.source),
            conversation_history=[
                {
                    "sender": message.sender_type,
                    "text": message.content,
                }
                for message in reversed(previous_messages)
            ],
            latest_message=text_body,
        )

        generation_config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=WhatsAppAgentResponse,
        )
        ai_response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=turn_prompt,
            config=generation_config,
        )
        structured_response = ai_response.parsed
        if not isinstance(structured_response, WhatsAppAgentResponse):
            if not ai_response.text:
                raise ValueError("Gemini returned no structured response")
            structured_response = WhatsAppAgentResponse.model_validate_json(ai_response.text)

        if structured_response.needs_human_escalation:
            logger.warning("WhatsApp escalation requested for lead %s", sender_id)
        else:
            logger.info("WhatsApp AI reply for lead %s: %s", sender_id, structured_response.reply_text)
        reply_text = structured_response.reply_text

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

def _legacy_process_whatsapp_message(payload: dict[str, Any]) -> None:
    """Run payload processing in FastAPI's background worker thread."""
    if payload.get("object") != "whatsapp_business_account":
        logger.info("Ignoring Meta webhook object type: %s", payload.get("object"))
        return
    try:
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        asyncio.run(_process_whatsapp_message(payload, client))
    except Exception:
        logger.exception("Failed to initialize or run WhatsApp background processing.")


async def _process_whatsapp_message(payload: dict[str, Any], client: genai.Client) -> None:
    """Process a Meta payload after acknowledging the webhook request."""
    db = SessionLocal()
    try:
        for entry in payload.get("entry", []):
            try:
                changes = entry.get("changes", [])
            except (AttributeError, KeyError, TypeError) as payload_err:
                logger.warning("Skipping malformed Meta entry: %s", payload_err)
                continue
            for change in changes:
                try:
                    value = change["value"]
                    metadata = value.get("metadata", {})
                    messages = value.get("messages", [])
                    contacts = value.get("contacts", [])
                except (AttributeError, KeyError, TypeError) as payload_err:
                    logger.warning("Skipping malformed Meta change: %s", payload_err)
                    continue
                for message in messages:
                    try:
                        with db.begin_nested():
                            await _handle_inbound_message(db, metadata, contacts, message, client)
                    except Exception as message_error:
                        logger.exception("Failed processing WhatsApp message; recording it in the DLQ.")
                        try:
                            db.add(WebhookDLQ(
                                provider=WebhookProvider.META,
                                payload=payload,
                                error_reason=str(message_error),
                                retry_count=0,
                                is_resolved=False,
                            ))
                            db.commit()
                        except Exception:
                            logger.exception("Could not record WhatsApp event in the DLQ.")
                            db.rollback()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Background WhatsApp payload processing failed.")
    finally:
        db.close()


@router.post("")
@router.post("/")
async def handle_whatsapp_webhook(
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Validate and acknowledge Meta webhook requests without waiting on AI."""
    await verify_whatsapp_signature(request)
    
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as parse_err:
        logger.warning("Failed to parse incoming WhatsApp webhook JSON: %s", parse_err)
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object")

    if not _has_fresh_meta_timestamps(payload):
        logger.warning("Rejected Meta webhook with missing, malformed, or stale event timestamp.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Stale webhook event")

    if not background_task_capacity.try_add(
        background_tasks,
        process_whatsapp_message,
        payload,
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background processing capacity is full",
        )
    return JSONResponse(status_code=200, content={"status": "ok"})