import hashlib
import hmac
import logging
import os
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from src.config import settings
from src.services.background_task_capacity import background_task_capacity

router = APIRouter(tags=["Webhooks - Campaign"])
logger = logging.getLogger("CampaignWebhook")

_IDEMPOTENCY_WINDOW_SECONDS = 24 * 60 * 60
redis_client: Redis = from_url(settings.REDIS_URL, decode_responses=True)


# Strict strings prevent implicit coercion, and bounded fields limit untrusted input.
# In particular, the short notes limit reduces the amount of attacker-controlled prompt text.
class InboundLeadPayload(BaseModel):
    """Validated and size-limited lead data accepted from campaign platforms."""

    model_config = ConfigDict(extra="forbid")

    lead_name: StrictStr = Field(max_length=50)
    # E.164 uses a leading plus, a nonzero country-code digit, and at most 15 digits.
    phone_number: Annotated[
        StrictStr,
        Field(pattern=r"^\+[1-9]\d{1,14}$"),
    ]
    campaign_source: StrictStr = Field(max_length=100)
    notes: Optional[StrictStr] = Field(default=None, max_length=250)


def trigger_outbound_ai_agent(payload: InboundLeadPayload) -> None:
    """Placeholder for dispatching a validated lead to the outbound AI workflow."""
    logger.info("Accepted campaign lead for outbound processing.")


async def verify_campaign_tenant_key(
    x_tenant_key: Annotated[Optional[str], Header(alias="X-Tenant-Key")] = None,
) -> None:
    """Fail closed unless the request carries the configured campaign secret."""
    configured_secret = os.getenv("CAMPAIGN_WEBHOOK_SECRET")
    if (
        not configured_secret
        or not x_tenant_key
        # Constant-time comparison avoids leaking secret-prefix information.
        or not hmac.compare_digest(
            x_tenant_key.encode("utf-8"),
            configured_secret.encode("utf-8"),
        )
    ):
        logger.warning("Rejected campaign webhook with missing or invalid tenant key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )


async def _reserve_lead_idempotency_key(phone_number: str) -> bool:
    """Atomically claim a lead key in shared Redis storage across all workers."""
    phone_hash = hashlib.sha256(phone_number.encode("utf-8")).hexdigest()
    key = f"campaign:webhook:lead:{phone_hash}"
    try:
        claimed = await redis_client.set(
            key,
            "1",
            ex=_IDEMPOTENCY_WINDOW_SECONDS,
            nx=True,
        )
    except RedisError as error:
        logger.error(
            "Campaign webhook idempotency backend unavailable (%s)",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook idempotency service unavailable",
        ) from error
    return bool(claimed)


@router.post("/webhooks/leads/inbound")
async def receive_campaign_lead(
    payload: InboundLeadPayload,
    background_tasks: BackgroundTasks,
    _: None = Depends(verify_campaign_tenant_key),
) -> dict[str, str]:
    """Authenticate, validate, and enqueue a lead from a campaign platform."""
    if not background_task_capacity.try_reserve():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background processing capacity is full",
        )

    reservation_transferred = False
    try:
        is_new_lead = await _reserve_lead_idempotency_key(payload.phone_number)
        if not is_new_lead:
            logger.info("Ignored duplicate campaign lead within the idempotency window.")
            return {"status": "accepted"}

        background_task_capacity.add_reserved(
            background_tasks,
            trigger_outbound_ai_agent,
            payload,
        )
        reservation_transferred = True
        return {"status": "accepted"}
    finally:
        if not reservation_transferred:
            background_task_capacity.release_reservation()
