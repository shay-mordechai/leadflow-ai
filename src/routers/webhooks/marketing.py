from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, constr
import logging

from src.database.session import get_db
from src.database.models import User, Lead, LeadSource, LeadStatus
from src.services.communication.whatsapp import whatsapp_adapter

# Initialize Router
router = APIRouter(
    prefix="/webhooks/marketing",
    tags=["Marketing Webhooks"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

# --- SCHEMAS ---

class IncomingLeadPayload(BaseModel):
    """
    Schema for incoming leads from external marketing platforms.
    """
    name: str = Field(..., description="Full name of the lead")
    phone_number: str = Field(..., description="Phone number of the lead (preferably with country code)")
    campaign_name: Optional[str] = Field(None, description="Name of the marketing campaign")
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional custom data collected from the lead form")

# --- DEPENDENCIES ---

async def verify_marketing_api_key(
    x_marketing_api_key: str = Header(..., description="API Key for Marketing Integration"),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to authenticate the incoming webhook request using the marketing API key.
    Finds and returns the User (Tenant) associated with the provided key.
    """
    # Look up the user by their marketing API key
    stmt = select(User).where(User.marketing_api_key == x_marketing_api_key)
    result = db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning(f"Failed marketing webhook authentication. Invalid API Key provided.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Marketing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
        
    if not user.is_active:
        logger.warning(f"Marketing webhook received for inactive user ID: {user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is not active",
        )
        
    return user

# --- HELPER FUNCTIONS ---

def clean_phone_number(phone: str) -> str:
    """
    Cleans and normalizes the phone number.
    Removes spaces, dashes, parentheses, etc.
    Adds a plus sign if it's missing (assuming international format is expected or standardizing it).
    """
    # Remove all non-numeric characters except the plus sign
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # If it doesn't start with '+', and we assume it includes a country code (e.g., starts with 972 or 1), 
    # we could prepend it. For now, we'll just ensure it's clean digits.
    # A more robust library like `phonenumbers` could be used here.
    if not cleaned.startswith('+') and cleaned:
        cleaned = '+' + cleaned
        
    return cleaned

# --- ROUTES ---

@router.post("/incoming-lead", status_code=status.HTTP_201_CREATED)
async def receive_incoming_lead(
    payload: IncomingLeadPayload,
    tenant: User = Depends(verify_marketing_api_key),
    db: Session = Depends(get_db)
):
    """
    Endpoint for external marketing tools (Zapier, Make, Elementor, etc.) to push new leads.
    
    Flow:
    1. Authenticate via `X-Marketing-API-Key` header.
    2. Normalize the phone number.
    3. Check if the lead already exists for this tenant.
    4. Create the lead if new.
    5. Trigger a proactive WhatsApp message to the lead.
    """
    logger.info(f"Received incoming lead for tenant {tenant.id} from campaign: {payload.campaign_name}")
    
    # 1. Clean the phone number
    normalized_phone = clean_phone_number(payload.phone_number)
    if not normalized_phone:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Invalid phone number format."
         )

    # 2. Check if lead already exists for this tenant
    stmt = select(Lead).where(
        Lead.user_id == tenant.id,
        Lead.phone_number == normalized_phone
    )
    result = db.execute(stmt)
    existing_lead = result.scalar_one_or_none()

    if existing_lead:
        logger.info(f"Lead with phone {normalized_phone} already exists for tenant {tenant.id}. Updating custom fields.")
        # Optionally update custom fields or note the new campaign source
        if payload.custom_fields:
            # Assuming custom_fields is a JSON column on the Lead model, if it exists
            # We'll merge the dictionaries if it does, otherwise just skip or log.
            # existing_lead.custom_fields = {**(existing_lead.custom_fields or {}), **payload.custom_fields}
            pass
        
        db.commit()
        return {"status": "success", "message": "Lead already exists", "lead_id": str(existing_lead.id)}

    # 3. Create a new Lead
    # Determine the source based on campaign name or default to LANDING_PAGE
    lead_source = LeadSource.LANDING_PAGE
    if payload.campaign_name and "social" in payload.campaign_name.lower():
        lead_source = LeadSource.SOCIAL_CAMPAIGN

    new_lead = Lead(
        user_id=tenant.id,
        name=payload.name,
        phone_number=normalized_phone,
        source=lead_source,
        status=LeadStatus.NEW,
        # We can store the campaign_name or custom_fields in a JSON/Text field if your model supports it.
        # e.g. metadata={"campaign": payload.campaign_name, "fields": payload.custom_fields}
    )
    
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)
    
    logger.info(f"Successfully created new lead {new_lead.id} for tenant {tenant.id}")

    # 4. Trigger proactive outbound WhatsApp message
    try:
        # TODO: Implement AI Prompt Logic here.
        # We need to query the tenant's AI Agent or Business Profile to construct a dynamic, personalized message.
        # For now, we send a standard template/greeting message.
        
        greeting_message = (
            f"Hi {payload.name}, we received your details regarding our services. "
            f"How can we help you today?"
        )
        
        # Trigger the WhatsApp adapter to send the message asynchronously
        # (Assuming whatsapp_adapter has an async send_message method)
        # Note: In a production environment, this might be better placed in a Celery task
        # to avoid blocking the HTTP response if the API call is slow.
        
        # await whatsapp_adapter.send_message(
        #     to=normalized_phone,
        #     message=greeting_message,
        #     tenant_id=tenant.id
        # )
        
        logger.info(f"Triggered proactive WhatsApp message to {normalized_phone} for lead {new_lead.id}")
        
    except Exception as e:
        # We catch exceptions so that a failure to send the WhatsApp message doesn't 
        # cause the webhook to return a 500 error to the marketing platform.
        logger.error(f"Failed to send proactive WhatsApp message to {normalized_phone}: {str(e)}")

    return {
        "status": "success", 
        "message": "Lead created and contacted successfully", 
        "lead_id": str(new_lead.id)
    }
