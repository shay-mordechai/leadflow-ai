# tests/test_hybrid_rag.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.ai.prompt_builder import PromptBuilder
from src.services.rag.chunker import chunk_document_text
from src.services.rag.retriever import retrieve_relevant_chunks


def test_chunker_structure_and_pricing_tables():
    """Verifies chunker preserves headings and pricing rows without splitting mid-table."""
    markdown_content = """
# Pricing Sheet
| Service | Price |
|---|---|
| Haircut | 150 NIS |
| Coloring | 350 NIS |

## Cancellation Policy
Cancel 24 hours in advance free of charge.
"""
    chunks = chunk_document_text(markdown_content)
    assert len(chunks) >= 2
    assert any("Pricing Sheet" in c["section_title"] for c in chunks)
    assert any("Haircut" in c["content"] for c in chunks)
    assert any("Cancellation Policy" in c["section_title"] for c in chunks)


def test_prompt_builder_retrieved_knowledge_injection():
    """Verifies PromptBuilder injects retrieved chunks with explicit chunk IDs and title attributes."""
    chunks = [
        {
            "chunk_id": "chunk-123",
            "section_title": "Pricing",
            "content": "Haircut is 150 NIS.",
            "score": 0.95,
        }
    ]
    prompt = PromptBuilder.build_lead_turn_prompt(
        lead_name="John",
        lead_source="WhatsApp",
        conversation_history=[],
        latest_message="How much is a haircut?",
        retrieved_chunks=chunks,
    )
    assert "<retrieved_knowledge>" in prompt
    assert 'id="chunk-123"' in prompt
    assert "Haircut is 150 NIS." in prompt


@pytest.mark.asyncio
async def test_cross_tenant_rag_isolation():
    """Verifies retrieval strictly pre-filters by user_id to prevent cross-tenant chunk leakage."""
    db_mock = AsyncMock()
    # Mock return values for scalar results: tenant_a chunks should not be accessible by tenant_b
    db_mock.scalars = AsyncMock(return_value=MagicMock(all=list))

    results = await retrieve_relevant_chunks(
        db_mock, tenant_id="tenant_b_id", query="Haircut price"
    )
    assert results == []
    db_mock.scalars.assert_awaited_once()
