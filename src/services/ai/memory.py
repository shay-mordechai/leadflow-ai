# src/services/ai/memory.py
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Lead, Message

logger = logging.getLogger("ConversationMemoryService")


class ConversationMemoryService:
    """
    Manages long-term conversation memory, rolling summaries, and sliding windows
    per lead with strict tenant isolation.
    """

    @staticmethod
    async def get_lead_memory(db: AsyncSession, tenant_id: Any, lead_id: Any) -> dict[str, Any]:
        """Loads conversation summary, extracted state, and recent messages for a lead."""
        lead = await db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.user_id == tenant_id).limit(1)
        )
        if lead is None:
            return {
                "conversation_summary": None,
                "extracted_state": {},
                "recent_history": [],
                "summary_message_count": 0,
            }

        recent_msgs = await db.scalars(
            select(Message)
            .where(Message.lead_id == lead_id)
            .order_by(Message.created_at.desc())
            .limit(6)
        )
        history = [
            {"sender": m.sender_type, "text": m.content} for m in reversed(recent_msgs.all())
        ]

        return {
            "conversation_summary": lead.conversation_summary,
            "extracted_state": lead.extracted_state or {},
            "recent_history": history,
            "summary_message_count": lead.summary_message_count or 0,
        }

    @staticmethod
    async def update_lead_summary(
        db: AsyncSession,
        tenant_id: Any,
        lead_id: Any,
        new_summary: str,
        new_extracted_state: dict[str, Any],
        new_message_count: int,
    ) -> None:
        """Atomically updates lead conversation memory with strict tenant filtering."""
        lead = await db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.user_id == tenant_id).limit(1)
        )
        if lead:
            lead.conversation_summary = new_summary
            lead.extracted_state = new_extracted_state
            lead.summary_message_count = new_message_count
            await db.commit()
            logger.info(f"Updated conversation memory for lead {lead_id}")
