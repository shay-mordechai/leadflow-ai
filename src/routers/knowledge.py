# src/routers/knowledge.py
import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.config import settings
from src.database.models import KnowledgeDocument, User
from src.database.session import get_db
from src.security.dependencies import get_current_user
from src.services.rag.ingestor import ingest_tenant_document

router = APIRouter(prefix="/api/v1/knowledge", tags=["Tenant Knowledge - Hybrid RAG"])
logger = logging.getLogger("KnowledgeRouter")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB limit
ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt"}


class KnowledgeDocumentResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    status: str
    chunk_count: int
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Uploads a tenant knowledge document (.pdf, .md, or .txt, max 5MB),
    sanitizes filename, runs async ingestion and embedding indexing,
    and increments the tenant Redis kb_version.
    Enforces strict multi-tenant isolation.
    """
    response.headers["X-Data-TTL"] = "1"
    if not file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed: {list(ALLOWED_EXTENSIONS)}",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File size exceeds 5 MB limit")

    safe_filename = os.path.basename(file.filename)
    content_type = file.content_type or "application/octet-stream"

    try:
        doc = await ingest_tenant_document(
            db=db,
            tenant_id=str(current_user.id),
            filename=safe_filename,
            content_type=content_type,
            raw_bytes=raw_bytes,
        )
        return {
            "status": "success",
            "message": "Document ingested and indexed successfully",
            "document_id": str(doc.id),
            "filename": doc.filename,
            "chunk_count": doc.chunk_count,
        }
    except Exception as e:
        logger.error(f"Document ingestion failed for tenant {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to ingest knowledge document")


@router.get("/documents")
async def list_knowledge_documents(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lists all indexed knowledge documents for the logged-in tenant.
    Enforces strict multi-tenant isolation by filtering exclusively by current_user.id.
    """
    response.headers["X-Data-TTL"] = "1"
    docs = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.user_id == str(current_user.id))
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "content_type": d.content_type,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.delete("/documents/{doc_id}", status_code=status.HTTP_200_OK)
async def delete_knowledge_document(
    request: Request,
    doc_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes a knowledge document and its associated chunks strictly where id == doc_id and user_id == current_user.id.
    Increments Redis kb_version to invalidate stale cache.
    """
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.user_id == str(current_user.id),
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Knowledge document not found")

    db.delete(doc)
    db.commit()

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.incr(f"tenant:{current_user.id}:kb_version")
        await r.close()
    except Exception as redis_err:
        logger.warning(f"Failed to increment Redis kb_version on document deletion: {redis_err}")

    logger.info(f"🗑️ Deleted knowledge document {doc_id} for tenant {current_user.email}")
    return {"status": "success", "message": "Document and chunks deleted successfully"}
