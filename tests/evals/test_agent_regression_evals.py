# tests/evals/test_agent_regression_evals.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.security.pii import mask_body, mask_phone
from src.services.ai.harness import AgentHarness


def test_pii_masking_helpers():
    """Verifies PII scrubbing helpers mask sensitive details correctly."""
    assert mask_phone("+972501234567") == "+972*****567"
    assert "REDACTED" in mask_body("Secret message content")


@pytest.mark.asyncio
async def test_golden_set_evaluation_mocked():
    """Runs evaluation samples from golden_set_hebrew.jsonl against the Agent Harness."""
    harness = AgentHarness()
    mock_response = MagicMock()
    mock_response.text = '{"reply_text": "בשמחה! אשמח לעזור.", "lead_intent": "INQUIRY", "lead_qualification_score": 50, "needs_human_escalation": false, "abstained": false}'
    harness.router = MagicMock()
    harness.router.redis = None
    harness.router.route_and_generate = AsyncMock(return_value=mock_response)

    with open("tests/evals/golden_set_hebrew.jsonl", "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        case = json.loads(line)
        res = await harness.execute_turn(
            tenant_id="tenant_eval",
            business_type=case["archetype"],
            business_name="Test Business",
            products_services="Testing services",
            custom_instructions=None,
            lead_name="Lead",
            lead_source="WHATSAPP",
            conversation_history=[],
            latest_message=case["input"],
        )
        assert isinstance(res, dict)
        assert "reply_text" in res
        assert "abstained" in res
        assert "needs_human_escalation" in res
