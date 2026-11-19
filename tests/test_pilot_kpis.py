# tests/test_pilot_kpis.py
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.database.models import KnowledgeDocument, Lead, LeadStatus, PendingApproval, User
from src.routers.insights import get_pilot_kpis


@pytest.mark.asyncio
async def test_pilot_kpis_aggregation_and_tenant_isolation():
    """Verifies get_pilot_kpis aggregates tenant metrics correctly and excludes other tenants."""
    current_user = User(
        id=uuid4(),
        name="Tenant A",
        email="tenant_a@example.com",
        hashed_password="hash",
    )
    # Mock database session
    db_mock = MagicMock()

    # Mock query returns for tenant_a
    lead_qualified = Lead(
        id=uuid4(), user_id=current_user.id, status=LeadStatus.QUALIFIED, ai_rating=1
    )
    lead_unqualified = Lead(
        id=uuid4(), user_id=current_user.id, status=LeadStatus.NEW, ai_rating=-1
    )

    approval_pending = PendingApproval(
        id=uuid4(), user_id=current_user.id, status="PENDING", action_type="BOOK"
    )
    approval_approved = PendingApproval(
        id=uuid4(), user_id=current_user.id, status="APPROVED", action_type="BOOK"
    )

    doc_indexed = KnowledgeDocument(
        id=uuid4(),
        user_id=str(current_user.id),
        status="INDEXED",
        chunk_count=3,
        filename="test.pdf",
        content_type="application/pdf",
    )

    # Set up filter query side effects
    def query_side_effect(model):
        q = MagicMock()
        if model == Lead:
            q.filter.return_value.all.return_value = [lead_qualified, lead_unqualified]
        elif model == PendingApproval:
            q.filter.return_value.count.return_value = 1
            q.filter.return_value.all.return_value = [approval_pending, approval_approved]
        elif model == KnowledgeDocument:
            q.filter.return_value.all.return_value = [doc_indexed]
        return q

    db_mock.query.side_effect = query_side_effect

    kpis = await get_pilot_kpis(current_user=current_user, db=db_mock)

    assert kpis["status"] == "success"
    assert kpis["total_leads"] == 2
    assert kpis["qualified_leads"] == 1
    assert kpis["qualification_rate_percentage"] == 50.0
    assert kpis["pending_approvals_count"] == 1
    assert kpis["approval_resolution_stats"]["APPROVED"] == 1
    assert kpis["ai_feedback_summary"]["thumbs_up"] == 1
    assert kpis["ai_feedback_summary"]["thumbs_down"] == 1
    assert kpis["knowledge_base_stats"]["indexed_documents"] == 1
    assert kpis["knowledge_base_stats"]["total_chunks"] == 3
