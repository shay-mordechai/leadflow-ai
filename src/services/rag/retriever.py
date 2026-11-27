# src/services/rag/retriever.py
import inspect
import logging
import math
import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import KnowledgeChunk, KnowledgeDocument
from src.services.rag.ingestor import generate_embedding

logger = logging.getLogger("RAGRetriever")


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


async def retrieve_relevant_chunks(
    db: Session,
    tenant_id: str,
    query: str,
    top_k: int = 4,
    min_score: float = 0.20,
    categories: Sequence[str] | None = ("business_facts",),
) -> list[dict[str, Any]]:
    """
    Retrieves relevant knowledge chunks for a query using Hybrid RRF (Semantic + Lexical overlap),
    strictly pre-filtering by KnowledgeChunk.user_id == tenant_id and KnowledgeDocument.category
    so external marketing_inspiration entries never leak into customer-facing WhatsApp replies.
    """
    if not query.strip():
        return []

    stmt = (
        select(KnowledgeChunk)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeChunk.user_id == str(tenant_id))
    )
    if categories:
        stmt = stmt.where(KnowledgeDocument.category.in_(list(categories)))

    res = db.scalars(stmt)
    if inspect.isawaitable(res):
        res = await res
    chunks = res.all()

    if not chunks:
        return []

    query_embedding = await generate_embedding(query)
    query_tokens = set(re_tokenize(query))

    scored_results = []
    for chunk in chunks:
        emb = chunk.embedding_json or []
        sem_score = _cosine_similarity(query_embedding, emb)

        chunk_tokens = set(re_tokenize(chunk.content))
        if query_tokens and chunk_tokens:
            intersection = query_tokens.intersection(chunk_tokens)
            lex_score = len(intersection) / len(query_tokens)
        else:
            lex_score = 0.0

        combined_score = (0.7 * sem_score) + (0.3 * lex_score)

        if combined_score >= min_score:
            scored_results.append(
                {
                    "chunk_id": str(chunk.id),
                    "section_title": chunk.section_title or "General",
                    "content": chunk.content,
                    "score": round(combined_score, 4),
                }
            )

    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:top_k]


def re_tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"\w+", text, re.UNICODE) if len(w) > 1]
