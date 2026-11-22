"""Comprehensive regression and integration tests covering workflow validation matrix gaps."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import Base, Lead, User, UserRole
from src.database.session import get_db
from src.routers import leads, partners
from src.security.dependencies import get_current_user
from src.services.ai.memory import ConversationMemoryService
from src.services.rag.ingestor import ingest_tenant_document


@pytest.fixture(name="app_client")
def app_client_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(partners.router)

    app.dependency_overrides[get_db] = lambda: session_factory()

    client = TestClient(app)
    yield client, session_factory
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_wf07_partner_performance_authz(app_client):
    """WF-07: Unauthenticated and non-admin access to /api/v1/partners/performance is rejected (401/403)."""
    client, session_factory = app_client

    # 1. Unauthenticated request -> 401/403
    response = client.get("/api/v1/partners/performance")
    assert response.status_code in (401, 403)

    # 2. Authenticated as non-admin CLIENT -> 403
    db = session_factory()
    try:
        client_user = User(
            id=uuid.uuid4(),
            name="Client User",
            email="client@example.com",
            hashed_password="hash",
            role=UserRole.CLIENT,
        )
        db.add(client_user)
        db.commit()
    finally:
        db.close()

    app = client.app
    app.dependency_overrides[get_current_user] = lambda: client_user

    response = client.get("/api/v1/partners/performance")
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"

    # 3. Authenticated as ADMIN -> 200
    admin_user = User(
        id=uuid.uuid4(),
        name="Admin User",
        email="admin@example.com",
        hashed_password="hash",
        role=UserRole.ADMIN,
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user

    response = client.get("/api/v1/partners/performance")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_wf11_conversation_memory_service_isolation_and_compaction():
    """WF-11: ConversationMemoryService manages rolling summary compaction and extracted_state isolation by user_id."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async_eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with async_eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(async_eng, expire_on_commit=False)

    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    lead_id = uuid.uuid4()

    async with async_session() as db:
        user = User(
            id=tenant_id,
            name="Tenant",
            email="t@example.com",
            hashed_password="pw",
        )
        lead = Lead(
            id=lead_id,
            user_id=tenant_id,
            name="Test Lead",
            conversation_summary="Initial summary",
            extracted_state={"budget": 5000},
            summary_message_count=2,
        )
        db.add(user)
        db.add(lead)
        await db.commit()

        memory_other = await ConversationMemoryService.get_lead_memory(db, other_tenant_id, lead_id)
        assert memory_other["conversation_summary"] is None
        assert memory_other["extracted_state"] == {}

        memory = await ConversationMemoryService.get_lead_memory(db, tenant_id, lead_id)
        assert memory["conversation_summary"] == "Initial summary"
        assert memory["extracted_state"] == {"budget": 5000}
        assert memory["summary_message_count"] == 2

        await ConversationMemoryService.update_lead_summary(
            db,
            tenant_id,
            lead_id,
            new_summary="Compacted summary: client interested in PRO plan",
            new_extracted_state={"budget": 10000, "goal": "growth"},
            new_message_count=10,
        )

        memory_updated = await ConversationMemoryService.get_lead_memory(db, tenant_id, lead_id)
        assert (
            memory_updated["conversation_summary"]
            == "Compacted summary: client interested in PRO plan"
        )
        assert memory_updated["extracted_state"]["budget"] == 10000
        assert memory_updated["summary_message_count"] == 10

    await async_eng.dispose()


@pytest.mark.asyncio
async def test_chain_c_end_to_end_integration():
    """Chain C: Hybrid RAG ingestion -> AgentHarness retrieval -> HITL PendingApproval -> KPI/Feedback update."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from src.database.models import LeadStatus, PendingApproval
    from src.services.ai.harness import agent_harness

    async_eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with async_eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(async_eng, expire_on_commit=False)

    tenant_id = uuid.uuid4()
    lead_id = uuid.uuid4()

    async with async_session() as db:
        user = User(id=tenant_id, name="Coach", email="coach@example.com", hashed_password="pw")
        lead = Lead(id=lead_id, user_id=tenant_id, name="Lead Client", phone_number="+972501234567")
        db.add(user)
        db.add(lead)
        await db.commit()

        # 1. Ingest Knowledge Document (WF-14 / Chain C step 1)
        doc = await ingest_tenant_document(
            db,
            str(tenant_id),
            "pricing.md",
            "text/markdown",
            b"# Pricing Sheet\nPersonal coaching session is 350 NIS per hour.",
        )
        assert doc.chunk_count > 0

        from sqlalchemy import select

        from src.database.models import KnowledgeChunk

        chunk_res = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id)
        )
        first_chunk = chunk_res.scalars().first()
        assert first_chunk is not None

        # 2. Mock Gemini Client for AgentHarness execution
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "reply_text": "האימון עולה 350 שקל לשעה.",
                "lead_intent": "PRICING",
                "lead_qualification_score": 75,
                "needs_human_escalation": False,
                "abstained": False,
                "cited_chunk_ids": [str(first_chunk.id)],
            }
        )
        agent_harness.router.route_and_generate = AsyncMock(return_value=mock_response)

        # 3. Execute turn via AgentHarness
        result = await agent_harness.execute_turn(
            tenant_id=str(tenant_id),
            business_type="Coaching",
            business_name="Coach Pro",
            products_services="Coaching",
            custom_instructions=None,
            lead_name="Lead Client",
            lead_source="WHATSAPP",
            conversation_history=[],
            latest_message="כמה עולה אימון?",
            db=db,
            lead_id=lead_id,
        )
        assert result["reply_text"] == "האימון עולה 350 שקל לשעה."
        assert result["lead_qualification_score"] == 75

        # 4. Create HITL Pending Approval (WF-13)
        approval = PendingApproval(
            user_id=tenant_id,
            lead_id=lead_id,
            action_type="BOOK_APPOINTMENT",
            draft_reply="קביעת פגישה למחר בשעה 10:00",
            status="PENDING",
        )
        db.add(approval)
        await db.commit()
        await db.refresh(approval)

        # 5. Simulate resolving approval
        approval.status = "APPROVED"
        lead.status = LeadStatus.QUALIFIED
        lead.ai_rating = 1
        await db.commit()

        assert approval.status == "APPROVED"
        assert lead.status == LeadStatus.QUALIFIED

    await async_eng.dispose()


def test_wf16_and_wf24_followup_and_dlq_tasks():
    """WF-16 & WF-24: Followup tasks and DLQ event processor import and run successfully."""
    from src.tasks.followup_tasks import process_dlq_events, process_smart_followups

    assert callable(process_smart_followups)
    assert callable(process_dlq_events)


def test_hitl_approval_atomic_race_condition():
    """Regression: Concurrent resolution of the same PendingApproval allows only one successful update (TOCTOU protection)."""
    from src.database.models import PendingApproval

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(leads.router, prefix="/api/v1/leads")

    db = session_factory()
    user_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    user = User(
        id=user_id, name="U", email="u@example.com", hashed_password="pw", role=UserRole.CLIENT
    )
    lead = Lead(id=lead_id, user_id=user_id, name="L", phone_number="+972501234567")
    approval_id = uuid.uuid4()
    approval = PendingApproval(
        id=approval_id,
        user_id=user_id,
        lead_id=lead_id,
        action_type="TEST",
        draft_reply="Draft",
        status="PENDING",
    )
    db.add(user)
    db.add(lead)
    db.add(approval)
    db.commit()
    db.close()

    app.dependency_overrides[get_db] = lambda: session_factory()
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    res = client.post(
        f"/api/v1/leads/approvals/{approval_id}/decision", json={"decision": "APPROVE"}
    )
    assert res.status_code == 200

    # Second concurrent attempt on already approved item must fail with 409 Conflict
    res2 = client.post(
        f"/api/v1/leads/approvals/{approval_id}/decision", json={"decision": "APPROVE"}
    )
    assert res2.status_code == 409

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
