import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from typing import Optional

# Professional English Comment: Initialize Router
router = APIRouter(tags=["Leads Management"])

# Professional English Comment: Configure local logger for this module
logger = logging.getLogger(__name__)

# Professional English Comment:
# Pydantic Model for incoming leads via Webhook (e.g., from Pagix Landing Pages).
# Enforces strict typing for data integrity.
class PagixLead(BaseModel):
    name: str = Field(..., min_length=2, title="Full Name")
    phone: str = Field(..., min_length=9, title="Phone Number")
    email: Optional[EmailStr] = Field(None, title="Email Address")
    source: str = Field(default="pagix_landing_page", title="Lead Source")

@router.post("/pagix", status_code=status.HTTP_201_CREATED)
async def receive_pagix_lead(lead: PagixLead):
    """
    Webhook Endpoint: Receives lead data from Pagix landing pages.

    Process:
    1. Validates payload via Pydantic.
    2. Logs the received data for audit purposes.
    3. (Future) Insert into database via Service layer.
    """
    try:
        # Professional English Comment:
        # In a real production scenario, avoid logging PII (Personally Identifiable Information)
        # directly without masking. For this demo, we log to verify connectivity.
        logger.info(f"New Lead Received via Webhook: {lead.name} | Source: {lead.source}")

        # Placeholder for Database insertion logic
        # e.g., await lead_service.create_lead(lead)

        return {
            "status": "success",
            "message": "Lead processed successfully",
            "lead_id": lead.phone[-4:]  # responding with partial ID for confirmation
        }

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error processing lead"
        )
