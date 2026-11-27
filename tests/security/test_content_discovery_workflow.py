"""
Security and workflow tests for Phase 3 & 4:
- Celery least-privilege routing (rag_read vs mutations) and weekly Beat schedule
- Tenant RLS context cleanup in discovery tasks
- End-to-end HITL approval -> categorized RAG ('marketing_inspiration') ingestion
- Anti-IDOR / BOLA enforcement between Tenant A and Tenant B
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import AuditLog, Base, BusinessProfile, ContentSuggestion, User
from src.database.session import current_tenant_id_var
from src.routers.insights import (
    BrandDNAUpdateRequest,
    ContentDecisionRequest,
    decide_content_suggestion,
    update_brand_dna,
)
from src.services.marketing.content_discovery import normalize_and_hash_url
from src.services.rag.ingestor import ingest_tenant_document
from src.services.rag.retriever import retrieve_relevant_chunks
from src.tasks.marketing_advisor import discover_tenant_content, persist_content_suggestions
from src.worker import celery_app


def test_content_discovery_celery_routing_and_beat_schedule():
    routes = celery_app.conf.task_routes
    assert routes["src.tasks.marketing_advisor.dispatch_weekly_content_discovery"] == {
        "queue": "rag_read"
    }
    assert routes["src.tasks.marketing_advisor.discover_tenant_content"] == {"queue": "rag_read"}
    assert routes["src.tasks.marketing_advisor.persist_content_suggestions"] == {
        "queue": "mutations"
    }
    assert "weekly-content-discovery" in celery_app.conf.beat_schedule
    assert (
        celery_app.conf.beat_schedule["weekly-content-discovery"]["task"]
        == "src.tasks.marketing_advisor.dispatch_weekly_content_discovery"
    )


def test_discover_tenant_content_resets_rls_context_on_error():
    initial_ctx = current_tenant_id_var.get()
    with patch("src.tasks.marketing_advisor.ReadOnlySessionLocal") as mock_ro:
        mock_ro.side_effect = RuntimeError("Simulated RO DB Failure")
        with pytest.raises(RuntimeError, match="Simulated RO DB Failure"):
            discover_tenant_content(str(uuid.uuid4()))
    assert current_tenant_id_var.get() == initial_ctx


def test_persist_content_suggestions_deduplicates_audits_and_notifies():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    tenant_id = uuid.uuid4()

    with session_local() as db:
        db.add(
            User(
                id=tenant_id,
                email="yael-owner@test.local",
                name="Yael",
                hashed_password="pw",
                personal_whatsapp="+972501112233",
            )
        )
        db.add(
            BusinessProfile(
                user_id=tenant_id,
                business_name="Yael Natural Makeup",
                business_type="Makeup Artist",
                content_discovery_enabled=True,
            )
        )
        db.commit()

    beauty_host = "beauty.example.com"
    norm = normalize_and_hash_url(f"https://{beauty_host}/natural-glow-prep")
    assert norm is not None
    candidate_dict = {
        "title": "הכנת עור לאיפור טבעי",
        "url": norm[0],
        "url_hash": norm[1],
        "summary_he": "טיפים פשוטים לעור זוהר בלי שכבות כבדות.",
        "draft_post_he": "פוסט מוכן לאינסטגרם על איפור טבעי ✨",
        "relevance_reason": "תואם לסגנון טבעי",
        "matched_keyword": "איפור טבעי לכלות",
        "source_provider": "tavily",
    }

    with (
        patch("src.tasks.marketing_advisor.SessionLocal", session_local),
        patch(
            "src.tasks.marketing_advisor.whatsapp_adapter.send_message", return_value=True
        ) as mock_wa,
    ):
        res1 = persist_content_suggestions(
            str(tenant_id), [candidate_dict], generated_keywords=["איפור טבעי לכלות"]
        )
        assert res1["created_count"] == 1
        assert mock_wa.call_count == 1

        # Re-running with the same url_hash must deduplicate and not re-spam WhatsApp
        res2 = persist_content_suggestions(str(tenant_id), [candidate_dict])
        assert res2["created_count"] == 0
        assert mock_wa.call_count == 1

    with session_local() as db:
        suggestions = (
            db.query(ContentSuggestion).filter(ContentSuggestion.user_id == tenant_id).all()
        )
        assert len(suggestions) == 1
        assert suggestions[0].status == "PENDING"
        profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == tenant_id).first()
        assert profile.search_keywords == ["איפור טבעי לכלות"]
        audits = (
            db.query(AuditLog)
            .filter(
                AuditLog.user_id == str(tenant_id),
                AuditLog.action == "CONTENT_SUGGESTIONS_DISCOVERED",
            )
            .all()
        )
        assert len(audits) == 2

    engine.dispose()


@pytest.mark.asyncio
async def test_hitl_approval_enforces_anti_idor_and_categorized_rag_isolation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    with session_local() as db:
        user_a = User(id=tenant_a_id, email="a@test.local", name="Yael", hashed_password="pw")
        user_b = User(id=tenant_b_id, email="b@test.local", name="Attacker", hashed_password="pw")
        db.add_all([user_a, user_b])
        db.commit()

        # 1. Configure Brand DNA + auto-generated keywords for Tenant A
        with patch(
            "src.routers.insights.generate_search_keywords",
            return_value=["איפור טבעי לכלות", "natural bridal skin prep"],
        ):
            dna_res = await update_brand_dna(
                payload=BrandDNAUpdateRequest(
                    brand_style="איפור טבעי השומר על תווי הפנים",
                    anti_positioning="ללא איפור כבד או מראה מסיכה",
                    content_pillars=["הכנת עור", "איפור כלות עדין"],
                    content_discovery_enabled=True,
                ),
                current_user=user_a,
                db=db,
            )
            assert dna_res["search_keywords"] == ["איפור טבעי לכלות", "natural bridal skin prep"]

        # 2. Seed one verified business fact + one PENDING content suggestion for Tenant A
        fixed_vec = [0.5] * 8
        beauty_host = "beauty.example.com"
        norm = normalize_and_hash_url(f"https://{beauty_host}/bridal-glow")
        assert norm is not None
        suggestion = ContentSuggestion(
            user_id=tenant_a_id,
            title="הכנת עור טבעית לפני איפור כלה",
            source_url=norm[0],
            url_hash=norm[1],
            matched_keyword="איפור טבעי לכלות",
            summary_he="מדריך להכנת עור זוהר ללא שכבות עבות.",
            draft_post_he="הסוד למראה כלה טבעי שומר על תווי הפנים ✨",
            status="PENDING",
        )
        db.add(suggestion)
        db.commit()

        # 3. Anti-IDOR check: Tenant B must receive 404 when attempting to decide Tenant A's suggestion
        with pytest.raises(HTTPException) as exc_info:
            await decide_content_suggestion(
                suggestion_id=str(suggestion.id),
                payload=ContentDecisionRequest(decision="APPROVE", add_to_rag=True),
                current_user=user_b,
                db=db,
            )
        assert exc_info.value.status_code == 404

        # 4. Tenant A approves -> ingested strictly into marketing_inspiration, never business_facts
        with (
            patch(
                "src.services.rag.ingestor.generate_embedding",
                new=AsyncMock(return_value=fixed_vec),
            ),
            patch(
                "src.services.rag.retriever.generate_embedding",
                new=AsyncMock(return_value=fixed_vec),
            ),
        ):
            await ingest_tenant_document(
                db=db,
                tenant_id=str(tenant_a_id),
                filename="official_prices.txt",
                content_type="text/plain",
                raw_bytes="איפור כלה טבעי מחיר רשמי 1800 שח".encode(),
                category="business_facts",
            )

            decision_res = await decide_content_suggestion(
                suggestion_id=str(suggestion.id),
                payload=ContentDecisionRequest(decision="APPROVE", add_to_rag=True),
                current_user=user_a,
                db=db,
            )
            assert decision_res["status"] == "APPROVED"
            assert decision_res["ingested_document_id"] is not None

            # Customer-facing default retrieval MUST NOT include approved marketing_inspiration
            support_hits = await retrieve_relevant_chunks(
                db=db,
                tenant_id=str(tenant_a_id),
                query="איפור כלה טבעי",
                top_k=5,
            )
            assert len(support_hits) == 1
            assert "1800" in support_hits[0]["content"]

            # Marketing retrieval explicitly includes both categories
            marketing_hits = await retrieve_relevant_chunks(
                db=db,
                tenant_id=str(tenant_a_id),
                query="איפור כלה טבעי",
                top_k=5,
                categories=("business_facts", "marketing_inspiration"),
            )
            assert len(marketing_hits) > len(support_hits)
            combined_marketing_text = " ".join(h["content"] for h in marketing_hits)
            assert "1800" in combined_marketing_text
            assert "הסוד למראה כלה טבעי" in combined_marketing_text

    engine.dispose()
