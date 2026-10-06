from typing import Literal

from pydantic import BaseModel, Field


class LeadExtraction(BaseModel):
    goal: str | None = Field(default=None, description="The customer's primary goal or requirement")
    preferred_time: str | None = Field(default=None, description="Preferred schedule or appointment time")


class WhatsAppAgentResponse(BaseModel):
    reply_text: str = Field(
        ...,
        max_length=600,
        description="A natural Hebrew WhatsApp reply in no more than 2-3 concise sentences.",
    )
    lead_intent: Literal["INQUIRY", "PRICING", "BOOKING", "COMPLAINT", "UNKNOWN"] = Field(
        ...,
        description="Lead intent classification.",
    )
    lead_qualification_score: int = Field(..., ge=0, le=100, description="Lead score from 0 to 100")
    needs_human_escalation: bool = Field(
        ...,
        description="True if the customer is angry, requests a human, or raises an out-of-scope issue.",
    )
    extracted_data: LeadExtraction = Field(default_factory=LeadExtraction)