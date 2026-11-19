# tests/test_tenant_tools_and_hitl.py
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.services.ai.prompt_builder import PromptBuilder
from src.services.ai.tools.calendar_tools import make_calendar_tools
from src.services.ai.tools.crm_tools import make_qualify_lead_tool


@pytest.mark.asyncio
async def test_calendar_tools_ssrf_and_format_rejection():
    """Verifies calendar tools reject URLs and invalid date/time formats (SSRF defense)."""
    db_mock = AsyncMock()
    tenant_id = uuid4()
    lead_id = uuid4()

    check_avail, propose_book = make_calendar_tools(db_mock, tenant_id, lead_id)

    # SSRF URL rejection in date_str
    with pytest.raises(ValueError, match="date_str must be a valid YYYY-MM-DD date"):
        await check_avail("http://169.254.169.254/latest/meta-data")

    with pytest.raises(ValueError, match="date_str must be a valid YYYY-MM-DD date"):
        propose_appointment_booking_url = "http://127.0.0.1"
        await propose_book(propose_appointment_booking_url, "12:00", "Consultation")

    # Invalid time format rejection
    with pytest.raises(ValueError, match="time_str must be a valid 24-hour HH:MM time"):
        await propose_book("2026-12-01", "25:70", "Consultation")


@pytest.mark.asyncio
async def test_crm_tool_bounds_validation():
    """Verifies qualify_lead tool validates budget and string lengths."""
    db_mock = AsyncMock()
    tenant_id = uuid4()
    lead_id = uuid4()

    qualify = make_qualify_lead_tool(db_mock, tenant_id, lead_id)

    with pytest.raises(ValueError, match="budget must be an integer"):
        await qualify(-100, "1 week", "Goal")

    with pytest.raises(ValueError, match="budget must be an integer"):
        await qualify(20_000_000, "1 week", "Goal")

    with pytest.raises(ValueError, match="timeframe must be a non-empty string"):
        await qualify(5000, "", "Goal")


def test_prompt_builder_tool_sync():
    """Verifies PromptBuilder includes tool instructions only when enabled_tools is provided."""
    prompt_without = PromptBuilder.build_system_instruction(
        business_type="Fitness",
        business_name="Gym",
        enabled_tools=(),
    )
    assert "No tools are currently enabled" in prompt_without
    assert "check_calendar_availability" not in prompt_without

    prompt_with = PromptBuilder.build_system_instruction(
        business_type="Fitness",
        business_name="Gym",
        enabled_tools=("check_calendar_availability", "propose_appointment_booking"),
    )
    assert "check_calendar_availability" in prompt_with
    assert "propose_appointment_booking" in prompt_with
