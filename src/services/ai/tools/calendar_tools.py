# src/services/ai/tools/calendar_tools.py
import json
import logging
import re
from datetime import date
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import AuditLog, Lead, PendingApproval

logger = logging.getLogger("CalendarTools")

_TIME_FORMAT = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _validate_tool_date(date_str: str) -> None:
    """Accept only canonical ISO dates as calendar-tool arguments, rejecting URLs/SSRF."""
    if not isinstance(date_str, str) or "://" in date_str or len(date_str) > 10:
        raise ValueError("date_str must be a valid YYYY-MM-DD date format without URLs")
    try:
        parsed_date = date.fromisoformat(date_str)
    except (TypeError, ValueError) as exc:
        raise ValueError("date_str must be a valid YYYY-MM-DD date") from exc
    if parsed_date.isoformat() != date_str:
        raise ValueError("date_str must be a valid YYYY-MM-DD date")


def make_calendar_tools(db: AsyncSession, tenant_id: Any, lead_id: Any):
    """Factory creating tenant-scoped calendar availability and appointment proposal tools."""

    async def check_calendar_availability(date_str: str) -> str:
        """
        Checks the business owner's calendar for available slots on a given date (YYYY-MM-DD).
        Args:
            date_str: Canonical ISO date (YYYY-MM-DD).
        """
        _validate_tool_date(date_str)
        logger.info(f"🤖 CALENDAR TOOL: check_calendar_availability for date {date_str}")
        return json.dumps(
            {
                "available_slots": ["09:00", "11:30", "15:00", "17:00"],
                "message": "These are the available slots. Ask the user which one they prefer.",
            }
        )

    async def propose_appointment_booking(date_str: str, time_str: str, service_name: str) -> str:
        """
        Proposes an appointment booking, submitting it for business owner verification (HITL).
        Args:
            date_str: Canonical ISO date (YYYY-MM-DD).
            time_str: 24-hour time (HH:MM).
            service_name: Name of the requested service or session.
        """
        _validate_tool_date(date_str)
        if not isinstance(time_str, str) or not _TIME_FORMAT.fullmatch(time_str):
            raise ValueError("time_str must be a valid 24-hour HH:MM time")
        if (
            not isinstance(service_name, str)
            or len(service_name.strip()) == 0
            or len(service_name) > 100
        ):
            raise ValueError("service_name must be a non-empty string of at most 100 characters")

        logger.info(
            f"🤖 CALENDAR TOOL: propose_appointment_booking for {date_str} {time_str} ({service_name})"
        )

        lead = await db.get(Lead, lead_id)
        if lead is None or str(lead.user_id) != str(tenant_id):
            raise ValueError("Lead not found or unauthorized access")

        draft_text = (
            f"בקשת קביעת פגישה בתאריך {date_str} בשעה {time_str} עבור שירות '{service_name}'."
        )
        payload = {"date": date_str, "time": time_str, "service": service_name}

        # Create PendingApproval record for HITL
        approval = PendingApproval(
            user_id=tenant_id,
            lead_id=lead_id,
            action_type="BOOK_APPOINTMENT",
            draft_reply=draft_text,
            action_payload=payload,
            status="PENDING",
        )
        db.add(approval)

        # Flag lead as requiring human verification
        stmt = (
            update(Lead)
            .where(Lead.id == lead_id, Lead.user_id == tenant_id)
            .values(requires_human=True, suggested_reply=draft_text)
        )
        await db.execute(stmt)

        db.add(
            AuditLog(
                user_id=str(tenant_id),
                action="AI_TOOL_PROPOSE_APPOINTMENT",
                details={"lead_id": str(lead_id), "date": date_str, "time": time_str},
            )
        )
        await db.commit()

        return json.dumps(
            {
                "status": "pending_approval",
                "message": "Appointment proposal submitted to business owner for approval. Inform the user that the request is noted and pending confirmation.",
            }
        )

    return check_calendar_availability, propose_appointment_booking
