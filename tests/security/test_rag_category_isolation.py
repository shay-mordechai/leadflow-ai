"""
Security tests verifying that external 'marketing_inspiration' RAG documents
never leak into default customer-facing WhatsApp RAG retrieval ('business_facts').
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, User
from src.services.rag.ingestor import ingest_tenant_document
from src.services.rag.retriever import retrieve_relevant_chunks


@pytest.mark.asyncio
async def test_marketing_inspiration_does_not_leak_into_customer_support_rag():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    tenant_id = uuid.uuid4()

    with session_local() as db:
        db.add(
            User(
                id=tenant_id,
                email="yael-makeup@test.local",
                name="Yael",
                hashed_password="pw",
            )
        )
        db.commit()

        fixed_vec = [0.5] * 8
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
            # 1. Reject unknown categories
            with pytest.raises(ValueError, match="Unsupported knowledge category"):
                await ingest_tenant_document(
                    db=db,
                    tenant_id=str(tenant_id),
                    filename="bad.txt",
                    content_type="text/plain",
                    raw_bytes=b"bad category payload",
                    category="untrusted_web",
                )

            # 2. Ingest verified business fact
            await ingest_tenant_document(
                db=db,
                tenant_id=str(tenant_id),
                filename="pricing.txt",
                content_type="text/plain",
                raw_bytes="איפור טבעי לכלות מחיר רשמי 1500 שח".encode(),
                category="business_facts",
            )

            # 3. Ingest approved external marketing inspiration
            await ingest_tenant_document(
                db=db,
                tenant_id=str(tenant_id),
                filename="web_trend.txt",
                content_type="text/plain",
                raw_bytes="איפור טבעי לכלות טרנד קיץ הכנת עור זוהר".encode(),
                category="marketing_inspiration",
            )

            # Default retrieval (WhatsApp customer bot) MUST only see business_facts
            support_chunks = await retrieve_relevant_chunks(
                db=db,
                tenant_id=str(tenant_id),
                query="איפור טבעי לכלות",
                top_k=5,
            )
            assert len(support_chunks) == 1
            assert "1500" in support_chunks[0]["content"]
            assert "טרנד קיץ" not in support_chunks[0]["content"]

            # Marketing worker retrieval explicitly requests both categories
            marketing_chunks = await retrieve_relevant_chunks(
                db=db,
                tenant_id=str(tenant_id),
                query="איפור טבעי לכלות",
                top_k=5,
                categories=("business_facts", "marketing_inspiration"),
            )
            assert len(marketing_chunks) == 2

    engine.dispose()
