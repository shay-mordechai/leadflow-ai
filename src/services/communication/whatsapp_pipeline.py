import json
import logging
import os
from typing import Any, Optional

import httpx
from google import genai
from google.genai import types
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
)
from src.database.session import AsyncSessionLocal
from src.schemas.ai_response import WhatsAppAgentResponse
from src.services.ai.prompt_builder import PromptBuilder

logger = logging.getLogger("WhatsAppPipeline")

STARTER_MESSAGE_LIMIT = 10
PRO_MESSAGE_LIMIT = 2000
MAX_AUTOMATED_TURNS = 15
MAX_OUTPUT_TOKENS = 512
GEMINI_REQUEST_TIMEOUT_MS = 7_000
GRAPH_API_VERSION = "v21.0"


def _create_gemini_client() -> genai.Client:
    """Create a client with a bounded network timeout for all Gemini operations."""
    return genai.Client(
        api_key=settings.GOOGLE_API_KEY,
        http_options=types.HttpOptions(timeout=GEMINI_REQUEST_TIMEOUT_MS),
    )


def _build_generation_config(system_instruction: str) -> types.GenerateContentConfig:
    """Build structured-output settings with an explicit token budget."""
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=WhatsAppAgentResponse,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.2,
    )


def _turn_limit_reached(inbound_turn_count: int) -> bool:
    """Return whether the conversation has reached the automated-turn safety cap."""
    return inbound_turn_count >= MAX_AUTOMATED_TURNS


async def _reserve_ai_message_credit(
    db: AsyncSession,
    user_id: Any,
    max_message_count: int,
) -> Optional[int]:
    """Atomically reserve one monthly AI message slot if the tenant has quota left."""
    statement = (
        update(User)
        .where(
            User.id == user_id,
            User.monthly_ai_messages < max_message_count,
        )
        .values(monthly_ai_messages=User.monthly_ai_messages + 1)
        .returning(User.monthly_ai_messages)
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def _release_ai_message_credit(db: AsyncSession, user_id: Any) -> bool:
    """Return a reserved usage slot after inference or delivery fails."""
    statement = (
        update(User)
        .where(
            User.id == user_id,
            User.monthly_ai_messages > 0,
        )
        .values(monthly_ai_messages=User.monthly_ai_messages - 1)
        .returning(User.monthly_ai_messages)
    )
    try:
        async with db.begin():
            result = await db.execute(statement)
            return result.scalar_one_or_none() is not None
    except Exception as error:
        logger.error(
            "Failed to release AI message reservation for user %s (%s)",
            user_id,
            type(error).__name__,
        )
        return False


def _digits_only(value: Optional[str]) -> str:
    return "".join(character for character in (value or "") if character.isdigit())


def _extract_text_body(message: dict[str, Any]) -> Optional[str]:
    message_type = message.get("type")
    if message_type == "text":
        body = (message.get("text") or {}).get("body")
        return body.strip() if isinstance(body, str) and body.strip() else None
    if message_type == "button":
        text = (message.get("button") or {}).get("text")
        return text.strip() if isinstance(text, str) and text.strip() else None
    if message_type == "interactive":
        interactive = message.get("interactive") or {}
        for reply_type in ("button_reply", "list_reply"):
            title = (interactive.get(reply_type) or {}).get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()
    return None


async def _resolve_tenant(
    db: AsyncSession,
    metadata: dict[str, Any],
) -> tuple[Optional[User], Optional[PhoneNumber]]:
    phone_number_id = (metadata.get("phone_number_id") or "").strip()
    display_phone = _digits_only(metadata.get("display_phone_number"))
    phone_record = None

    if phone_number_id:
        phone_record = await db.scalar(
            select(PhoneNumber)
            .where(PhoneNumber.provider_id == phone_number_id)
            .limit(1)
        )

    if phone_record is None and display_phone:
        phone_tail = display_phone[-9:] if len(display_phone) >= 9 else display_phone
        phone_record = await db.scalar(
            select(PhoneNumber)
            .where(PhoneNumber.number.contains(phone_tail))
            .limit(1)
        )

    if phone_record is not None:
        return await db.get(User, phone_record.owner_id), phone_record

    if display_phone:
        phone_tail = display_phone[-9:] if len(display_phone) >= 9 else display_phone
        user = await db.scalar(
            select(User)
            .where(User.assigned_phone_number.contains(phone_tail))
            .limit(1)
        )
        return user, None
    return None, None


async def send_whatsapp_message(
    phone_number_id: str,
    recipient_phone: str,
    text: str,
) -> Optional[str]:
    """Send a text message through Meta Graph API and return its message ID."""
    token = (os.getenv("WHATSAPP_API_TOKEN") or "").strip()
    clean_phone = _digits_only(recipient_phone)
    if not token:
        raise RuntimeError("WHATSAPP_API_TOKEN is not configured")
    if not phone_number_id or not clean_phone or not text.strip():
        raise ValueError("Phone number ID, recipient, and message text are required")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as http_client:
        response = await http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()

    response_payload = response.json()
    messages = response_payload.get("messages") or []
    return messages[0].get("id") if messages and isinstance(messages[0], dict) else None


async def _prepare_message_context(
    db: AsyncSession,
    metadata: dict[str, Any],
    contacts: list[dict[str, Any]],
    message: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    external_id = message.get("id")
    if not isinstance(external_id, str) or not external_id.strip():
        logger.warning("Skipping Meta message without an external message ID")
        return "ignored_missing_message_id", {}

    existing_id = await db.scalar(
        select(Message.id).where(Message.external_id == external_id).limit(1)
    )
    if existing_id:
        logger.warning("Ignoring duplicate Meta WhatsApp message id=%s", external_id)
        return "duplicate", {}

    sender_id = _digits_only(message.get("from"))
    text_body = _extract_text_body(message)
    if not sender_id:
        logger.warning("Skipping Meta message without sender number id=%s", external_id)
        return "ignored_incomplete_message", {}
    if not text_body:
        logger.info("Ignoring unsupported or empty Meta message type=%s id=%s", message.get("type"), external_id)
        return "ignored_unsupported_type", {}

    contact_profile = ((contacts[0] or {}).get("profile") or {}) if contacts else {}
    sender_name = contact_profile.get("name") or "Guest"
    user, phone_record = await _resolve_tenant(db, metadata)
    if user is None:
        logger.warning("Received message for unassigned number: %s", metadata.get("display_phone_number"))
        return "ignored_unassigned_number", {}

    agent = await db.scalar(
        select(AIAgent).where(AIAgent.user_id == user.id).limit(1)
    )
    if agent is None or not agent.is_active:
        logger.info("AI agent disabled or missing for %s", metadata.get("display_phone_number"))
        return "agent_disabled", {}

    sender_tail = sender_id[-9:] if len(sender_id) >= 9 else sender_id
    lead = await db.scalar(
        select(Lead)
        .where(Lead.user_id == user.id, Lead.phone_number.contains(sender_tail))
        .limit(1)
    )
    if lead is None:
        lead = Lead(
            user_id=user.id,
            name=sender_name,
            phone_number=sender_id,
            source=LeadSource.WHATSAPP,
            status=LeadStatus.IN_PROGRESS,
            needs_followup=False,
        )
        db.add(lead)
        await db.flush()
    elif lead.status == LeadStatus.NEW:
        lead.status = LeadStatus.IN_PROGRESS
        lead.needs_followup = False

    inbound_message = Message(
        lead_id=lead.id,
        sender_type="user",
        content=text_body,
        external_id=external_id,
    )
    db.add(inbound_message)
    await db.flush()

    if lead.bot_active is False:
        logger.info("Muted lead %s (human takeover); inbound message saved", sender_id)
        return "muted", {}

    inbound_turn_count = await db.scalar(
        select(func.count(Message.id)).where(
            Message.lead_id == lead.id,
            Message.sender_type == "user",
        )
    )
    if _turn_limit_reached(inbound_turn_count or 0):
        lead.bot_active = False
        lead.requires_human = True
        logger.warning("Automated-turn limit reached for lead %s; escalating to a human", lead.id)
        return "turn_limit_reached", {
            "phone_number_id": (
                metadata.get("phone_number_id")
                or (phone_record.provider_id if phone_record else None)
                or settings.WHATSAPP_PHONE_ID
            ),
            "sender_id": sender_id,
            "limit_reply": "העברתי את השיחה לנציג אנושי שיחזור אליך בהקדם.",
            "needs_human_escalation": True,
        }

    max_message_limit = PRO_MESSAGE_LIMIT if user.plan_tier == PlanTier.PRO else STARTER_MESSAGE_LIMIT
    reserved_message_count = await _reserve_ai_message_credit(
        db,
        user.id,
        max_message_limit,
    )
    if reserved_message_count is None:
        return "limit_exceeded", {
            "lead_id": lead.id,
            "user_id": user.id,
            "sender_id": sender_id,
            "phone_number_id": (
                metadata.get("phone_number_id")
                or (phone_record.provider_id if phone_record else None)
                or settings.WHATSAPP_PHONE_ID
            ),
            "limit_reply": "מערכת המענה האוטומטי מושבתת זמנית עקב הגעה למגבלת ההודעות החודשית.",
        }

    business_profile = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id).limit(1)
    )
    recent_messages = await db.scalars(
        select(Message)
        .where(Message.lead_id == lead.id, Message.id != inbound_message.id)
        .order_by(Message.created_at.desc())
        .limit(6)
    )
    history = [
        {"sender": recent.sender_type, "text": recent.content}
        for recent in reversed(recent_messages.all())
    ]
    system_instruction = PromptBuilder.build_system_instruction(
        business_type=(
            (business_profile.business_type if business_profile else None)
            or user.business_type
            or "General"
        ),
        business_name=(
            (business_profile.business_name if business_profile else None)
            or user.business_name
            or "העסק שלנו"
        ),
        products_services=(business_profile.products_services if business_profile else None),
        custom_instructions=(
            (business_profile.custom_instructions if business_profile else None)
            or agent.system_prompt
        ),
    )
    lead_turn_prompt = PromptBuilder.build_lead_turn_prompt(
        lead_name=sender_name,
        lead_source=str(lead.source.value if hasattr(lead.source, "value") else lead.source),
        conversation_history=history,
        latest_message=text_body,
    )
    return "ready", {
        "external_id": external_id,
        "lead_id": lead.id,
        "user_id": user.id,
        "sender_id": sender_id,
        "phone_number_id": (
            metadata.get("phone_number_id")
            or (phone_record.provider_id if phone_record else None)
            or settings.WHATSAPP_PHONE_ID
        ),
        "system_instruction": system_instruction,
        "lead_turn_prompt": lead_turn_prompt,
    }


async def _process_single_message(
    db: AsyncSession,
    metadata: dict[str, Any],
    contacts: list[dict[str, Any]],
    message: dict[str, Any],
    client: Any,
) -> str:
    try:
        async with db.begin():
            result, context = await _prepare_message_context(db, metadata, contacts, message)
    except IntegrityError:
        logger.warning("Concurrent duplicate Meta WhatsApp message id=%s", message.get("id"))
        return "duplicate"

    if result in {"limit_exceeded", "turn_limit_reached"}:
        try:
            await send_whatsapp_message(
                context["phone_number_id"],
                context["sender_id"],
                context["limit_reply"],
            )
        except Exception:
            logger.exception("Meta API failed while sending message-limit notice")
            return "meta_send_failed"
        return result
    if result != "ready":
        return result

    try:
        response = await client.models.generate_content(
            model="gemini-2.5-flash",
            contents=context["lead_turn_prompt"],
            config=_build_generation_config(context["system_instruction"]),
        )
        structured_output = response.parsed
        if not isinstance(structured_output, WhatsAppAgentResponse):
            raise ValueError("Gemini did not return a parsed WhatsAppAgentResponse")
    except Exception as ai_error:
        logger.error(
            "Gemini inference failed for inbound message id=%s (%s)",
            message.get("id"),
            type(ai_error).__name__,
        )
        await _release_ai_message_credit(db, context["user_id"])
        return "gemini_failed"

    post_inference_result: Optional[str] = None
    try:
        async with db.begin():
            lead = await db.get(Lead, context["lead_id"])
            if lead is None:
                logger.error("Lead %s disappeared before response dispatch", context["lead_id"])
                post_inference_result = "lead_missing"
            elif lead.bot_active is False:
                logger.info("Human takeover began during inference for lead %s; suppressing reply", lead.id)
                post_inference_result = "muted_during_inference"
            else:
                lead.qualification_score = structured_output.lead_qualification_score
                if structured_output.needs_human_escalation:
                    lead.bot_active = False
                    lead.requires_human = True
                    logger.warning("Human handoff required for lead %s", lead.id)
    except Exception:
        logger.exception("Failed to update qualification or escalation state for lead %s", context["lead_id"])
        await _release_ai_message_credit(db, context["user_id"])
        return "database_update_failed"
    if post_inference_result is not None:
        await _release_ai_message_credit(db, context["user_id"])
        return post_inference_result

    try:
        outbound_id = await send_whatsapp_message(
            context["phone_number_id"],
            context["sender_id"],
            structured_output.reply_text,
        )
    except Exception:
        logger.exception("Meta Graph API send failed for inbound message id=%s", message.get("id"))
        await _release_ai_message_credit(db, context["user_id"])
        return "meta_send_failed"

    try:
        async with db.begin():
            db.add(Message(
                lead_id=context["lead_id"],
                sender_type="bot",
                content=structured_output.reply_text,
                external_id=outbound_id,
            ))
    except Exception:
        logger.exception("Meta sent reply but database sync failed for lead %s", context["lead_id"])
        return "database_sync_failed"

    logger.info("WhatsApp reply sent for lead %s (outbound_id=%s)", context["lead_id"], outbound_id)
    return "ai_replied"


async def process_whatsapp_message(payload: dict[str, Any]) -> None:
    """Process a Meta webhook payload asynchronously after HTTP acknowledgment."""
    if payload.get("object") != "whatsapp_business_account":
        logger.info("Ignoring Meta webhook object type: %s", payload.get("object"))
        return

    try:
        async with _create_gemini_client().aio as client:
            async with AsyncSessionLocal() as db:
                for entry in payload.get("entry", []):
                    for change in entry.get("changes", []):
                        try:
                            value = change["value"]
                            metadata = value.get("metadata", {})
                            messages = value.get("messages", [])
                            contacts = value.get("contacts", [])
                        except (AttributeError, KeyError, TypeError):
                            logger.exception("Skipping malformed Meta webhook change")
                            continue

                        for message in messages:
                            try:
                                await _process_single_message(
                                    db,
                                    metadata,
                                    contacts,
                                    message,
                                    client,
                                )
                            except Exception:
                                logger.exception("Unhandled WhatsApp message processing failure")
                                await db.rollback()
    except Exception:
        logger.exception("WhatsApp background pipeline failed")