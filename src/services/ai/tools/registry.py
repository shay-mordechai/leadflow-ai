# src/services/ai/tools/registry.py
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.ai.tools.calendar_tools import (
    make_calendar_tools,
)
from src.services.ai.tools.crm_tools import make_qualify_lead_tool


def build_tenant_tools(
    db: AsyncSession, tenant_id: str, lead_id: str
) -> tuple[list[Callable[..., Any]], list[str]]:
    """
    Builds tenant-scoped and lead-scoped tool callables bound via closures,
    preventing IDOR and binding the verified server identity.
    """
    check_avail, propose_book = make_calendar_tools(db, tenant_id, lead_id)
    qualify = make_qualify_lead_tool(db, tenant_id, lead_id)

    tools = [check_avail, propose_book, qualify]
    tool_names = [
        "check_calendar_availability",
        "propose_appointment_booking",
        "qualify_lead",
    ]
    return tools, tool_names


# Backward compatibility exports for legacy engine references
from src.services.ai.tools.calendar_tools import (
    check_calendar_availability as legacy_check_calendar,
)
from src.services.ai.tools.crm_tools import make_qualify_lead_tool as legacy_qualify_factory

AI_TOOLS = [legacy_check_calendar, legacy_qualify_factory]
