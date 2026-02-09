# src/routers/webhooks/whatsapp.py
import logging
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse

from src.config import settings

router = APIRouter(tags=["Webhooks - WhatsApp"])
logger = logging.getLogger("WhatsAppWebhook")

@router.get("/")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
):
    """
    Meta (Facebook) Verification Handshake.
    """
    verify_token = settings.WHATSAPP_VERIFY_TOKEN

    if mode == "subscribe" and token == verify_token:
        logger.info("✅ WhatsApp Webhook Verified successfully.")
        return PlainTextResponse(content=challenge)
    
    logger.warning("❌ WhatsApp Verification Failed: Invalid Token.")
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/")
async def whatsapp_event_listener(request: Request):
    """
    Receives incoming WhatsApp messages/statuses.
    """
    try:
        data = await request.json()
        logger.info(f"💬 WhatsApp Event: {data}")
        return {"status": "received"}
    except Exception as e:
        logger.error(f"🔥 WhatsApp Webhook Error: {e}")
        return {"status": "error"}