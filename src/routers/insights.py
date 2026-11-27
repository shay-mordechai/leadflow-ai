# src/routers/insights.py
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.models import KnowledgeDocument, Lead, LeadStatus, PendingApproval, User
from src.database.session import get_db
from src.security.dependencies import get_current_user
from src.services.marketing.strategy import (
    build_virtual_cmo_recommendations,
    update_strategy_weights,
)

router = APIRouter(prefix="/api/v1/insights", tags=["Marketing Insights - Virtual CMO"])
logger = logging.getLogger("MarketingInsights")


@router.get("/marketing-report")
async def get_virtual_cmo_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Virtual CMO & Marketing Insights Workflow:
    Analyzes all tenant leads over the past 6 months, extracts common trends,
    conversion rates, objection patterns, and provides actionable marketing recommendations.
    Enforces strict multi-tenant isolation by filtering exclusively by current_user.id.
    """
    try:
        six_months_ago = datetime.now(UTC) - timedelta(days=180)

        # 1. Fast SQL count for total 6-month leads
        total_leads = (
            db.query(func.count(Lead.id))
            .filter(
                Lead.user_id == current_user.id,
                Lead.created_at >= six_months_ago,
            )
            .scalar()
        ) or 0

        if total_leads == 0:
            return {
                "status": "success",
                "period": "Last 6 Months",
                "total_leads_analyzed": 0,
                "conversion_rate": 0.0,
                "recommendations": [
                    "אין מספיק נתונים כרגע לניתוח שיווקי. צבר לפחות 10 לידים כדי לקבל תובנות עומק."
                ],
                "trending_services": [],
            }

        # 2. Bounded projection query (max 500 leads)
        leads_query = (
            db.query(Lead.summary_text, Lead.status, Lead.ai_rating, Lead.created_at)
            .filter(
                Lead.user_id == current_user.id,
                Lead.created_at >= six_months_ago,
            )
            .order_by(Lead.created_at.desc())
            .limit(500)
            .all()
        )

        qualified_leads = sum(
            1 for l in leads_query if l.status == LeadStatus.QUALIFIED or l.ai_rating == 1
        )
        conversion_rate = round((qualified_leads / len(leads_query)) * 100, 1)

        # Aggregate lead summaries and common interest patterns
        service_mentions: dict[str, int] = {}
        for lead in leads_query:
            summary = (lead.summary_text or "").lower()
            # Simple keyword extraction or categorization for demo insights
            if "מחיר" in summary or "עלות" in summary:
                service_mentions["שאלות מחיר ותקציב"] = (
                    service_mentions.get("שאלות מחיר ותקציב", 0) + 1
                )
            if "פגישה" in summary or "ייעוץ" in summary:
                service_mentions["בקשות לפגישת ייעוץ"] = (
                    service_mentions.get("בקשות לפגישת ייעוץ", 0) + 1
                )
            if "דחוף" in summary or "מהר" in summary:
                service_mentions["פניות בדחיפות גבוהה"] = (
                    service_mentions.get("פניות בדחיפות גבוהה", 0) + 1
                )

        sorted_trends = sorted(service_mentions.items(), key=lambda x: x[1], reverse=True)
        trending_services = [{"topic": item[0], "mentions": item[1]} for item in sorted_trends]

        # Generate Virtual CMO Recommendations (centralized in strategy.py)
        recommendations = build_virtual_cmo_recommendations(
            conversion_rate=conversion_rate,
            price_mentions=service_mentions.get("שאלות מחיר ותקציב", 0),
            total_leads=total_leads,
        )

        logger.info(f"📊 Virtual CMO report generated successfully for Tenant {current_user.email}")

        return {
            "status": "success",
            "period": "Last 6 Months",
            "total_leads_analyzed": total_leads,
            "qualified_leads": qualified_leads,
            "conversion_rate_percentage": conversion_rate,
            "trending_services": trending_services,
            "recommendations": recommendations,
        }

    except Exception as e:
        logger.error(f"Failed to generate marketing insights report: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating marketing insights.",
        )


@router.get("/pilot-kpis")
async def get_pilot_kpis(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Pilot KPI Observability Endpoint:
    Returns real-time database-backed pilot metrics for the logged-in tenant:
    - Total leads and qualification rate
    - Pending HITL approvals count and resolution breakdown
    - AI satisfaction rate (thumbs up/down)
    - Knowledge base stats (indexed docs and chunks)
    Enforces strict multi-tenant isolation by filtering exclusively by current_user.id.
    """
    try:
        tenant_id = str(current_user.id)

        # 1. Leads & Qualification
        leads = db.query(Lead).filter(Lead.user_id == current_user.id).all()
        total_leads = len(leads)
        qualified_leads = sum(1 for l in leads if l.status == LeadStatus.QUALIFIED)
        qualification_rate = (
            round((qualified_leads / total_leads * 100), 1) if total_leads > 0 else 0.0
        )

        # 2. HITL Pending Approvals & Resolutions
        pending_approvals_count = (
            db.query(PendingApproval)
            .filter(PendingApproval.user_id == current_user.id, PendingApproval.status == "PENDING")
            .count()
        )

        all_approvals = (
            db.query(PendingApproval).filter(PendingApproval.user_id == current_user.id).all()
        )
        approval_resolution_stats = {"APPROVED": 0, "EDITED": 0, "REJECTED": 0}
        for app in all_approvals:
            if app.status in approval_resolution_stats:
                approval_resolution_stats[app.status] += 1

        # 3. AI Feedback Summary (Thumbs Up vs Down)
        thumbs_up = sum(1 for l in leads if l.ai_rating == 1)
        thumbs_down = sum(1 for l in leads if l.ai_rating == -1)
        total_rated = thumbs_up + thumbs_down
        satisfaction_rate = round((thumbs_up / total_rated * 100), 1) if total_rated > 0 else 100.0

        # 4. Knowledge Base Stats
        docs = db.query(KnowledgeDocument).filter(KnowledgeDocument.user_id == tenant_id).all()
        indexed_docs = sum(1 for d in docs if d.status == "INDEXED")
        total_chunks = sum(d.chunk_count for d in docs)

        return {
            "status": "success",
            "total_leads": total_leads,
            "qualified_leads": qualified_leads,
            "qualification_rate_percentage": qualification_rate,
            "pending_approvals_count": pending_approvals_count,
            "approval_resolution_stats": approval_resolution_stats,
            "ai_feedback_summary": {
                "thumbs_up": thumbs_up,
                "thumbs_down": thumbs_down,
                "satisfaction_rate_percentage": satisfaction_rate,
            },
            "knowledge_base_stats": {
                "indexed_documents": indexed_docs,
                "total_chunks": total_chunks,
            },
        }

    except Exception as e:
        logger.error(f"Failed to fetch pilot KPIs for tenant {current_user.email}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching pilot KPIs.",
        )


# =============================================================================
# Guided Brand DNA & Keyword-Driven Content Discovery (Human-in-the-Loop RAG)
# =============================================================================
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from src.database.models import AuditLog, BusinessProfile, ContentSuggestion
from src.services.marketing.content_discovery import (
    BrandDNA,
    generate_search_keywords,
    sanitize_untrusted_text,
)
from src.services.rag.ingestor import ingest_tenant_document
from src.tasks.marketing_advisor import discover_tenant_content


class BrandDNAUpdateRequest(BaseModel):
    brand_style: str = Field(
        default="",
        max_length=1000,
        description="Distinctive business style and aesthetic approach.",
    )
    anti_positioning: str = Field(
        default="",
        max_length=1000,
        description="Styles, methods, or topics the business explicitly avoids.",
    )
    content_pillars: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Core educational or promotional themes for social content.",
    )
    search_keywords: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Optional explicit search keywords; leave null or set regenerate_keywords=true to auto-generate.",
    )
    content_discovery_enabled: bool = Field(
        default=False,
        description="Opt-in flag enabling weekly web trend discovery.",
    )
    regenerate_keywords: bool = Field(
        default=False,
        description="Force AI keyword generation from Brand DNA.",
    )


class ContentDecisionRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    add_to_rag: bool = Field(
        default=True,
        description="When APPROVED, ingest content into marketing_inspiration RAG category.",
    )
    edited_post_he: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional owner edits to the drafted Hebrew post before saving.",
    )


@router.get("/brand-dna")
async def get_brand_dna(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the tenant's guided Brand DNA and keyword discovery configuration."""
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    if not profile:
        return {
            "brand_style": "",
            "anti_positioning": "",
            "content_pillars": [],
            "search_keywords": [],
            "content_discovery_enabled": False,
        }
    return {
        "brand_style": profile.brand_style or "",
        "anti_positioning": profile.anti_positioning or "",
        "content_pillars": profile.content_pillars or [],
        "search_keywords": profile.search_keywords or [],
        "content_discovery_enabled": bool(profile.content_discovery_enabled),
    }


@router.put("/brand-dna")
async def update_brand_dna(
    payload: BrandDNAUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates guided Brand DNA fields and generates/saves sanitized search keywords."""
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    if not profile:
        profile = BusinessProfile(
            id=uuid.uuid4(),
            user_id=current_user.id,
            business_name=current_user.business_name or current_user.name or "My Business",
            business_type=current_user.business_type or "General",
        )
        db.add(profile)

    profile.brand_style = sanitize_untrusted_text(payload.brand_style, max_len=1000)
    profile.anti_positioning = sanitize_untrusted_text(payload.anti_positioning, max_len=1000)
    profile.content_pillars = [
        sanitize_untrusted_text(p, max_len=100) for p in payload.content_pillars if p.strip()
    ]
    profile.content_discovery_enabled = payload.content_discovery_enabled

    if payload.search_keywords is not None and not payload.regenerate_keywords:
        profile.search_keywords = [
            sanitize_untrusted_text(k, max_len=120) for k in payload.search_keywords if k.strip()
        ]
    elif payload.regenerate_keywords or (
        payload.content_discovery_enabled and not profile.search_keywords
    ):
        brand = BrandDNA(
            business_name=profile.business_name or "My Business",
            business_type=profile.business_type or "General",
            brand_style=profile.brand_style or "",
            anti_positioning=profile.anti_positioning or "",
            content_pillars=profile.content_pillars or [],
            products_services=profile.products_services or "",
            ai_tone=profile.ai_tone or "Professional",
        )
        profile.search_keywords = generate_search_keywords(brand, max_keywords=6)

    db.commit()
    db.refresh(profile)

    return {
        "status": "updated",
        "brand_style": profile.brand_style or "",
        "anti_positioning": profile.anti_positioning or "",
        "content_pillars": profile.content_pillars or [],
        "search_keywords": profile.search_keywords or [],
        "content_discovery_enabled": bool(profile.content_discovery_enabled),
    }


@router.get("/content-suggestions")
async def list_content_suggestions(
    status_filter: Literal["PENDING", "APPROVED", "REJECTED"] | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists keyword-discovered content suggestions strictly scoped to the authenticated tenant."""
    query = db.query(ContentSuggestion).filter(ContentSuggestion.user_id == current_user.id)
    if status_filter:
        query = query.filter(ContentSuggestion.status == status_filter)
    items = query.order_by(ContentSuggestion.created_at.desc()).limit(50).all()

    return {
        "status": "success",
        "count": len(items),
        "suggestions": [
            {
                "id": str(item.id),
                "title": item.title,
                "source_url": item.source_url,
                "matched_keyword": item.matched_keyword,
                "source_provider": item.source_provider,
                "summary_he": item.summary_he,
                "draft_post_he": item.draft_post_he,
                "relevance_reason": item.relevance_reason,
                "status": item.status,
                "ingested_document_id": (
                    str(item.ingested_document_id) if item.ingested_document_id else None
                ),
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
            }
            for item in items
        ],
    }


@router.post("/content-suggestions/discover", status_code=status.HTTP_202_ACCEPTED)
async def trigger_content_discovery(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Triggers an asynchronous read-only content discovery scan for the authenticated tenant."""
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    if not profile or (not profile.search_keywords and not profile.brand_style):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please configure Brand DNA or search keywords before running discovery.",
        )

    discover_tenant_content.delay(str(current_user.id))
    return {"status": "queued", "tenant_id": str(current_user.id)}


@router.post("/content-suggestions/{suggestion_id}/decision")
async def decide_content_suggestion(
    suggestion_id: str,
    payload: ContentDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Human-in-the-loop approval endpoint.
    Enforces strict tenant ownership (anti-IDOR) and ingests approved topics exclusively into
    the 'marketing_inspiration' RAG category so customer-facing WhatsApp facts stay isolated.
    """
    try:
        parsed_suggestion_id = uuid.UUID(suggestion_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid suggestion ID format.",
        )

    suggestion = (
        db.query(ContentSuggestion)
        .filter(
            ContentSuggestion.id == parsed_suggestion_id,
            ContentSuggestion.user_id == current_user.id,
        )
        .first()
    )
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content suggestion not found.",
        )

    if suggestion.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Content suggestion already reviewed ({suggestion.status}).",
        )

    now_utc = datetime.now(UTC)
    suggestion.reviewed_at = now_utc

    # Update self-learning strategy weights on BusinessProfile if matched_keyword exists
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    effective_decision = payload.decision
    if (
        payload.decision == "APPROVE"
        and payload.edited_post_he is not None
        and payload.edited_post_he.strip()
    ):
        effective_decision = "EDITED"

    if profile and suggestion.matched_keyword:
        profile.strategy_weights = update_strategy_weights(
            profile.strategy_weights,
            suggestion.matched_keyword,
            effective_decision,
        )
        db.add(profile)

    if payload.decision == "REJECT":
        suggestion.status = "REJECTED"
        db.add(
            AuditLog(
                user_id=str(current_user.id),
                action="CONTENT_SUGGESTION_REJECTED",
                details={
                    "suggestion_id": str(suggestion.id),
                    "keyword": suggestion.matched_keyword,
                },
            )
        )
        db.commit()
        return {
            "status": "REJECTED",
            "suggestion_id": str(suggestion.id),
            "ingested_document_id": None,
        }

    # APPROVE path
    if payload.edited_post_he is not None and payload.edited_post_he.strip():
        suggestion.draft_post_he = sanitize_untrusted_text(payload.edited_post_he, max_len=2000)

    suggestion.status = "APPROVED"
    ingested_doc_id: str | None = None

    if payload.add_to_rag:
        md_lines = [
            f"# {suggestion.title}",
            "",
            f"Keyword: {suggestion.matched_keyword or 'N/A'}",
            "",
            "## Summary",
            suggestion.summary_he,
            "",
            "## Approved Draft Post",
            suggestion.draft_post_he,
            "",
        ]
        md_content = "\n".join(md_lines)
        doc = await ingest_tenant_document(
            db=db,
            tenant_id=str(current_user.id),
            filename=f"marketing_inspiration_{suggestion.url_hash[:12]}.md",
            content_type="text/markdown",
            raw_bytes=md_content.encode("utf-8"),
            category="marketing_inspiration",
        )
        suggestion.ingested_document_id = doc.id
        ingested_doc_id = str(doc.id)

    db.add(
        AuditLog(
            user_id=str(current_user.id),
            action="CONTENT_SUGGESTION_APPROVED",
            details={
                "suggestion_id": str(suggestion.id),
                "ingested_document_id": ingested_doc_id,
                "rag_category": "marketing_inspiration" if ingested_doc_id else None,
            },
        )
    )
    db.commit()

    return {
        "status": "APPROVED",
        "suggestion_id": str(suggestion.id),
        "ingested_document_id": ingested_doc_id,
    }
