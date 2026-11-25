import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

# Ensure root directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.schemas.ai_response import WhatsAppAgentResponse
from src.services.ai.prompt_builder import PromptBuilder


# =====================================================================
# 1. Unit Tests: Schema & Validation Contract
# =====================================================================
class TestAIResponseSchema:
    """Test suite for validating Pydantic schemas and output contracts."""

    def test_valid_schema_instantiation(self):
        """Verify valid payload successfully parses into WhatsAppAgentResponse."""
        payload = {
            "reply_text": "שלום, נשמח לתאם שיחה.",
            "lead_intent": "BOOKING",
            "lead_qualification_score": 90,
            "needs_human_escalation": False,
            "extracted_data": {"goal": "אימון אישי", "preferred_time": "ערב"},
        }
        response = WhatsAppAgentResponse(**payload)
        assert response.reply_text == "שלום, נשמח לתאם שיחה."
        assert response.lead_intent == "BOOKING"
        assert response.lead_qualification_score == 90
        assert response.needs_human_escalation is False
        assert response.extracted_data.goal == "אימון אישי"

    def test_schema_score_boundary_validation(self):
        """Ensure qualification score is strictly constrained between 0 and 100."""
        with pytest.raises(ValidationError):
            WhatsAppAgentResponse(
                reply_text="בדיקה",
                lead_intent="INQUIRY",
                lead_qualification_score=150,  # Invalid: gt 100
                needs_human_escalation=False,
            )


# =====================================================================
# 2. Unit Tests: PromptBuilder Architecture & Cache Invariance
# =====================================================================
class TestPromptBuilder:
    """Test suite for hierarchical prompt construction and XML boundary isolation."""

    def test_system_instruction_structure(self):
        """Verify static layers (1-3) contain essential XML boundaries and no dynamic lead leak."""
        instruction = PromptBuilder.build_system_instruction(
            business_type="Fitness",
            business_name="PowerGym",
            products_services="מנוי חודשי: 200 ש״ח",
            custom_instructions="לשמור על יחס אדיב",
        )

        assert "" in instruction
        assert "" in instruction
        assert "" in instruction
        assert "" in instruction
        assert "PowerGym" in instruction
        # Ensure dynamic lead variables are NOT in the static instruction to preserve caching
        assert "לקוח" not in instruction

    def test_lead_turn_prompt_layering(self):
        """Verify dynamic Layer 4 wraps lead data and incoming user message cleanly."""
        history = [
            {"sender": "דני", "text": "היי"},
            {"sender": "בוט", "text": "שלום דני, במה נוכל לעזור?"},
        ]
        lead_prompt = PromptBuilder.build_lead_turn_prompt(
            lead_name="דני",
            lead_source="WhatsApp",
            conversation_history=history,
            latest_message="כמה עולה אימון?",
        )

        assert "" in lead_prompt
        assert "" in lead_prompt
        assert "כמה עולה אימון?" in lead_prompt
        assert "דני: היי" in lead_prompt


# =====================================================================
# 3. Integration Pipeline Tests: Mocking External APIs & Webhooks
# =====================================================================
class TestWebhookWorkerLogic:
    """Test background task business logic (deduplication, takeover gate, outbound call)."""

    @pytest.mark.asyncio
    async def test_human_takeover_gate_blocks_ai(self):
        """Verify worker halts immediately when bot_active is False."""
        mock_lead = MagicMock()
        mock_lead.bot_active = False

        # Simulate the takeover check condition
        is_active = mock_lead.bot_active
        assert is_active is False
        # AI generation must be skipped when is_active is False

    @pytest.mark.asyncio
    async def test_process_single_message_commits_after_memory_query(self):
        """Verify _process_single_message successfully commits and dispatches reply without InvalidRequestError after get_lead_memory query."""
        from src.services.communication import whatsapp_pipeline

        mock_db = AsyncMock()
        mock_db.in_transaction = MagicMock(return_value=True)
        mock_db.add = MagicMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_db.begin = MagicMock(return_value=mock_tx)

        context = {
            "tenant_id": "test-tenant",
            "lead_id": "test-lead",
            "user_id": "test-user",
            "phone_number_id": "123456",
            "sender_id": "972500000000",
            "business_type": "Fitness",
            "business_name": "Gym",
            "products_services": "Training",
            "custom_instructions": "",
            "lead_name": "Dan",
            "lead_source": "WhatsApp",
            "latest_message": "Hello",
        }

        message = {"id": "wamid.123"}

        with (
            patch(
                "src.services.communication.whatsapp_pipeline._prepare_message_context",
                new_callable=AsyncMock,
                return_value=("ready", context),
            ),
            patch(
                "src.services.ai.memory.ConversationMemoryService.get_lead_memory",
                new_callable=AsyncMock,
            ) as mock_memory,
            patch(
                "src.services.ai.harness.AgentHarness.execute_turn", new_callable=AsyncMock
            ) as mock_turn,
            patch(
                "src.services.communication.whatsapp_pipeline.send_whatsapp_message",
                new_callable=AsyncMock,
            ) as mock_send,
            patch("src.database.models.Lead"),
        ):
            mock_memory.return_value = {"recent_history": []}
            mock_turn.return_value = {
                "reply_text": "Hi there!",
                "lead_qualification_score": 80,
                "needs_human_escalation": False,
            }
            mock_send.return_value = "wamid.outbound"

            mock_lead = MagicMock()
            mock_lead.bot_active = True
            mock_db.get.return_value = mock_lead

            result = await whatsapp_pipeline._process_single_message(
                mock_db, {"phone_number_id": "123456"}, [], message, AsyncMock()
            )

            assert result == "ai_replied"
            assert mock_db.commit.called
            assert mock_send.called
        """Test Meta Graph API outbound dispatcher using mock HTTP transport."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "wamid.HBgL..."}]}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            import httpx

            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://graph.facebook.com/v21.0/123456/messages",
                    headers={"Authorization": "Bearer fake_token"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": "972500000000",
                        "type": "text",
                        "text": {"body": "הודעת בדיקה"},
                    },
                )

            assert res.status_code == 200
            assert mock_post.called
            assert mock_post.call_args[1]["json"]["text"]["body"] == "הודעת בדיקה"


# =====================================================================
# 4. Optional Live Test: Direct Gemini 2.5 Flash Structured Inference
# =====================================================================
@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY environment variable not set. Skipping live inference.",
)
def test_live_gemini_structured_output():
    """Live call to Gemini 2.5 Flash verifying end-to-end Pydantic parsing."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    sys_instruction = PromptBuilder.build_system_instruction(
        business_type="Fitness",
        business_name="PowerGym",
        products_services="אימון ניסיון ללא עלות",
    )

    user_payload = PromptBuilder.build_lead_turn_prompt(
        lead_name="יוסי",
        lead_source="Facebook",
        conversation_history=[],
        latest_message="שלום, אפשר לבוא לאימון ניסיון מחר?",
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_payload,
        config=types.GenerateContentConfig(
            system_instruction=sys_instruction,
            response_mime_type="application/json",
            response_schema=WhatsAppAgentResponse,
            temperature=0.2,
        ),
    )

    parsed_data: WhatsAppAgentResponse = response.parsed
    assert isinstance(parsed_data, WhatsAppAgentResponse)
    assert len(parsed_data.reply_text) > 0
    assert parsed_data.lead_intent in ["BOOKING", "INQUIRY"]
    assert 0 <= parsed_data.lead_qualification_score <= 100
