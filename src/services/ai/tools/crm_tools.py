# src/services/ai/tools/crm_tools.py
import json
import logging
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import AuditLog, Lead, LeadStatus

logger = logging.getLogger("CRMTools")


def make_qualify_lead_tool(db: AsyncSession, tenant_id: Any, lead_id: Any):
    """Factory creating a tenant-scoped and lead-scoped qualify_lead tool closure."""

    async def qualify_lead(budget: int, timeframe: str, goal: str) -> str:
        """
        Saves the lead's budget, timeframe, and goal to qualify them securely.
        Args:
            budget: Lead budget amount (0 to 10,000,000).
            timeframe: Expected timeline (max 60 chars).
            goal: Customer primary goal (max 200 chars).
        """
        if not isinstance(budget, int) or budget < 0 or budget > 10_000_000:
            raise ValueError("budget must be an integer between 0 and 10,000,000")
        if not isinstance(timeframe, str) or len(timeframe.strip()) == 0 or len(timeframe) > 60:
            raise ValueError("timeframe must be a non-empty string of at most 60 characters")
        if not isinstance(goal, str) or len(goal.strip()) == 0 or len(goal) > 200:
            raise ValueError("goal must be a non-empty string of at most 200 characters")

        logger.info(f"🤖 CRM TOOL: qualify_lead called for lead {lead_id} under tenant {tenant_id}")

        # Fetch lead and ensure strict multi-tenant isolation
        lead = await db.get(Lead, lead_id)
        if lead is None or str(lead.user_id) != str(tenant_id):
            raise ValueError("Lead not found or unauthorized access")

        existing_state = lead.extracted_state or {}
        existing_state.update({"budget": budget, "timeframe": timeframe, "goal": goal})

        stmt = (
            update(Lead)
            .where(Lead.id == lead_id, Lead.user_id == tenant_id)
            .values(status=LeadStatus.QUALIFIED, extracted_state=existing_state)
        )
        await db.execute(stmt)

        # Audit log (no raw PII)
        db.add(
            AuditLog(
                user_id=str(tenant_id),
                action="AI_TOOL_QUALIFY_LEAD",
                details={"lead_id": str(lead_id), "status": "QUALIFIED"},
            )
        )
        await db.commit()

        return json.dumps(
            {
                "status": "qualified",
                "message": "Lead details saved and qualified successfully.",
            }
        )

    return qualify_lead
