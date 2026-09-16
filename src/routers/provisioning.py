import re
import httpx
import logging
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import User as Tenant
from src.config import settings

router = APIRouter(prefix="/api/v1/provisioning", tags=["Provisioning - B2B"])
logger = logging.getLogger("Provisioning")

@router.post("/webhook/twilio/sms")
async def twilio_sms_webhook(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    message_body = form_data.get("Body", "")
    to_number = form_data.get("To", "")

    # Extract 6-digit verification code
    match = re.search(r'\b(\d{6})\b', message_body)
    if not match:
        return {"status": "ignored", "reason": "No verification code found"}

    verification_code = match.group(1)

    # Locate tenant by their assigned WhatsApp number
    tenant = db.query(Tenant).filter(Tenant.assigned_phone_number == to_number).first()
    if not tenant or not tenant.whatsapp_access_token:
        logger.warning(f"Webhook received SMS for unknown or unconfigured number {to_number}")
        return {"error": "Unknown destination or missing Meta credentials"}

    url = f"https://graph.facebook.com/v19.0/{tenant.whatsapp_phone_number_id}/verify_code"
    headers = {"Authorization": f"Bearer {tenant.whatsapp_access_token}"}
    payload = {"code": verification_code}
    
    try:
        response = httpx.post(url, headers=headers, data=payload)
        response.raise_for_status()
        logger.info(f"✅ WhatsApp number {to_number} verified automatically!")
        return {"status": "success", "message": "Verified automatically with Meta"}
    except Exception as e:
        logger.error(f"❌ Meta verification failed: {str(e)}")
        return {"status": "failed", "error": str(e)}
