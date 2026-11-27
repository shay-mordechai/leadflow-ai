# src/tasks/marketing_advisor.py
import asyncio
import logging
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task

from src.database.models import (
    AuditLog,
    BusinessProfile,
    ContentSuggestion,
    KnowledgeChunk,
    Lead,
    LeadStatus,
    MeetingSession,
    Message,
    SubscriptionStatus,
    Tag,
    User,
)
from src.database.session import (
    ReadOnlySessionLocal,
    SessionLocal,
    reset_current_tenant_context,
    set_current_tenant_context,
)
from src.services.ai.engine import ai_engine
from src.services.communication.whatsapp import whatsapp_adapter
from src.services.marketing.content_discovery import (
    BrandDNA,
    discover_content_candidates,
    generate_search_keywords,
    sanitize_untrusted_text,
)
from src.services.marketing.strategy import (
    build_fallback_weekly_digest,
    build_weekly_digest_prompt,
    build_whatsapp_discovery_preview,
)

logger = logging.getLogger("MarketingAdvisorTask")


def _sanitize_untrusted_text(raw_text: str, max_len: int = 400) -> str:
    """Sanitizes untrusted DB/customer text to mitigate indirect prompt injection."""
    return sanitize_untrusted_text(raw_text, max_len=max_len)


def _build_brand_dna(tenant_user: User | None, profile: BusinessProfile | None) -> BrandDNA:
    """Constructs a BrandDNA dataclass from tenant User and BusinessProfile records."""
    business_name = (
        (profile.business_name if profile and profile.business_name else None)
        or (tenant_user.business_name if tenant_user else None)
        or "העסק שלך"
    )
    business_type = (
        (profile.business_type if profile and profile.business_type else None)
        or (tenant_user.business_type if tenant_user else None)
        or "General"
    )
    pillars = (
        profile.content_pillars if profile and isinstance(profile.content_pillars, list) else []
    )
    return BrandDNA(
        business_name=business_name,
        business_type=business_type,
        brand_style=(profile.brand_style if profile and profile.brand_style else ""),
        anti_positioning=(profile.anti_positioning if profile and profile.anti_positioning else ""),
        content_pillars=[str(p) for p in pillars if p],
        products_services=(
            profile.products_services if profile and profile.products_services else ""
        ),
        ai_tone=(profile.ai_tone if profile and profile.ai_tone else "Professional"),
    )


@shared_task(name="src.tasks.marketing_advisor.dispatch_weekly_marketing_digests")
def dispatch_weekly_marketing_digests() -> dict[str, Any]:
    """Scans for all active and trial tenants in the read-only database and dispatches individual asynchronous marketing digest tasks."""
    logger.info("📢 Starting weekly marketing digest dispatch across active tenants.")
    dispatched_tenants: list[str] = []
    with ReadOnlySessionLocal() as db:
        try:
            active_users = (
                db.query(User.id)
                .filter(
                    User.is_active.is_(True),
                    User.subscription_status.in_(
                        [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]
                    ),
                )
                .all()
            )
            for (user_id,) in active_users:
                tenant_id_str = str(user_id)
                analyze_tenant_marketing.delay(tenant_id_str)
                dispatched_tenants.append(tenant_id_str)
            logger.info("Successfully dispatched %d marketing digests.", len(dispatched_tenants))
            return {
                "status": "success",
                "dispatched_count": len(dispatched_tenants),
                "tenants": dispatched_tenants,
            }
        except Exception as exc:
            logger.error("Failed to dispatch weekly marketing digests: %s", exc)
            raise


@shared_task(name="src.tasks.marketing_advisor.analyze_tenant_marketing")
def analyze_tenant_marketing(tenant_id: str) -> dict[str, Any]:
    """Analyzes tenant metrics, Brand DNA, RAG knowledge base, and recent customer questions under read-only RLS context."""
    try:
        parsed_uuid = uuid.UUID(str(tenant_id))
    except (ValueError, TypeError) as exc:
        logger.error("Invalid tenant_id format supplied to marketing analysis: %s", exc)
        return {"status": "error", "reason": "Invalid tenant UUID"}
    tenant_token = set_current_tenant_context(str(parsed_uuid))
    try:
        with ReadOnlySessionLocal() as db:
            cutoff_date = datetime.now(UTC) - timedelta(days=7)
            recent_leads = (
                db.query(Lead)
                .filter(Lead.user_id == parsed_uuid, Lead.created_at >= cutoff_date)
                .all()
            )
            status_breakdown: dict[str, int] = {}
            source_breakdown: dict[str, int] = {}
            for lead in recent_leads:
                s_key = lead.status.value if hasattr(lead.status, "value") else str(lead.status)
                status_breakdown[s_key] = status_breakdown.get(s_key, 0) + 1
                src_key = lead.source.value if hasattr(lead.source, "value") else str(lead.source)
                source_breakdown[src_key] = source_breakdown.get(src_key, 0) + 1

            tags = db.query(Tag).filter(Tag.user_id == parsed_uuid).all()
            tag_summary = []
            for tag in tags:
                tag_leads_count = len(tag.leads) if tag.leads else 0
                tag_summary.append({"tag_name": tag.name, "lead_count": tag_leads_count})

            recent_sessions = (
                db.query(MeetingSession)
                .filter(MeetingSession.user_id == parsed_uuid)
                .order_by(MeetingSession.created_at.desc())
                .limit(5)
                .all()
            )
            session_summaries = [
                _sanitize_untrusted_text(s.summary or s.transcript or "", max_len=300)
                for s in recent_sessions
                if s.summary or s.transcript
            ]

            stale_leads_count = (
                db.query(Lead)
                .filter(
                    Lead.user_id == parsed_uuid,
                    Lead.needs_followup.is_(True),
                    Lead.status != LeadStatus.QUALIFIED,
                )
                .count()
            )

            # Retrieve tenant business profile & RAG knowledge chunks (business_facts + approved marketing_inspiration)
            tenant_user = db.query(User).filter(User.id == parsed_uuid).first()
            profile = (
                db.query(BusinessProfile).filter(BusinessProfile.user_id == parsed_uuid).first()
            )
            brand = _build_brand_dna(tenant_user, profile)
            business_name = brand.business_name
            products_services = _sanitize_untrusted_text(brand.products_services, max_len=800)

            rag_rows = (
                db.query(KnowledgeChunk)
                .filter(KnowledgeChunk.user_id == parsed_uuid)
                .order_by(KnowledgeChunk.chunk_index.asc())
                .limit(10)
                .all()
            )
            rag_snippets = [
                f"- [{_sanitize_untrusted_text(c.section_title or 'General', 80)}]: "
                f"{_sanitize_untrusted_text(c.content, 450)}"
                for c in rag_rows
                if c.content
            ]

            # Retrieve recent inbound customer questions to ground content in real demand
            recent_msg_rows = (
                db.query(Message.content)
                .join(Lead, Message.lead_id == Lead.id)
                .filter(
                    Lead.user_id == parsed_uuid,
                    Message.sender_type == "user",
                    Message.created_at >= cutoff_date,
                )
                .order_by(Message.created_at.desc())
                .limit(15)
                .all()
            )
            customer_questions = [
                f"- {_sanitize_untrusted_text(content, 200)}"
                for (content,) in recent_msg_rows
                if content and len(content.strip()) > 3
            ]

            metrics = {
                "total_new_leads_7d": len(recent_leads),
                "status_breakdown": status_breakdown,
                "source_breakdown": source_breakdown,
                "tag_summary": tag_summary,
                "stale_leads_count": stale_leads_count,
                "session_summaries_sample": session_summaries[:3],
                "rag_chunks_used": len(rag_snippets),
                "customer_questions_sampled": len(customer_questions),
            }

            rag_block = (
                "\n".join(rag_snippets) if rag_snippets else "No uploaded RAG documents yet."
            )
            questions_block = (
                "\n".join(customer_questions[:8])
                if customer_questions
                else "No recent customer questions recorded."
            )

            prompt = build_weekly_digest_prompt(
                business_name=_sanitize_untrusted_text(brand.business_name, 120),
                business_type=_sanitize_untrusted_text(brand.business_type, 80),
                ai_tone=_sanitize_untrusted_text(brand.ai_tone, 60),
                brand_style=_sanitize_untrusted_text(brand.brand_style, 300),
                anti_positioning=_sanitize_untrusted_text(brand.anti_positioning, 300),
                products_services=products_services,
                rag_block=rag_block,
                questions_block=questions_block,
                metrics=metrics,
            )

            digest_text = ""
            try:
                ai_result = ai_engine.generate_raw_analysis(prompt=prompt)
                if isinstance(ai_result, dict):
                    digest_text = ai_result.get("reply_text") or ai_result.get("summary") or ""
            except Exception as ai_exc:
                logger.warning(
                    "AI engine marketing generation failed, using fallback digest: %s", ai_exc
                )
            if not digest_text:
                digest_text = build_fallback_weekly_digest(
                    business_name=business_name,
                    total_new_leads=len(recent_leads),
                    stale_leads_count=stale_leads_count,
                )
            logger.info(
                "Successfully analyzed marketing metrics & RAG content for tenant %s", tenant_id
            )
            deliver_marketing_digest.delay(str(parsed_uuid), digest_text, metrics)
            return {"status": "analyzed", "tenant_id": tenant_id, "metrics": metrics}
    except Exception as exc:
        logger.error("Error analyzing tenant marketing for %s: %s", tenant_id, exc)
        raise
    finally:
        reset_current_tenant_context(tenant_token)


@shared_task(name="src.tasks.marketing_advisor.deliver_marketing_digest")
def deliver_marketing_digest(tenant_id: str, digest_text: str, metrics: dict) -> dict[str, Any]:
    """Writes immutable AuditLog entry under write-permission RLS context and delivers digest via WhatsApp."""
    try:
        parsed_uuid = uuid.UUID(str(tenant_id))
    except (ValueError, TypeError) as exc:
        logger.error("Invalid tenant_id format supplied to digest delivery: %s", exc)
        return {"status": "error", "reason": "Invalid tenant UUID"}
    tenant_token = set_current_tenant_context(str(parsed_uuid))
    try:
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == parsed_uuid).first()
            if not user:
                logger.warning("Tenant user %s not found during digest delivery.", tenant_id)
                return {"status": "error", "reason": "User not found"}
            audit_entry = AuditLog(
                user_id=str(parsed_uuid),
                action="MARKETING_DIGEST_GENERATED",
                details={
                    "digest_length": len(digest_text),
                    "metrics": metrics,
                    "whatsapp_target": user.personal_whatsapp,
                },
            )
            db.add(audit_entry)
            db.commit()
            if user.personal_whatsapp:
                success = whatsapp_adapter.send_message(
                    to_phone=user.personal_whatsapp, text=digest_text
                )
                if success:
                    logger.info(
                        "Successfully delivered marketing digest to owner WhatsApp for tenant %s",
                        tenant_id,
                    )
                else:
                    logger.warning(
                        "Failed sending marketing digest via WhatsApp adapter for tenant %s",
                        tenant_id,
                    )
            else:
                logger.info(
                    "Tenant %s has no personal_whatsapp configured; audit log recorded only.",
                    tenant_id,
                )
            return {"status": "delivered", "tenant_id": tenant_id}
    except Exception as exc:
        logger.error("Error delivering marketing digest for %s: %s", tenant_id, exc)
        raise
    finally:
        reset_current_tenant_context(tenant_token)


@shared_task(name="src.tasks.marketing_advisor.dispatch_weekly_content_discovery")
def dispatch_weekly_content_discovery() -> dict[str, Any]:
    """Scans read-only DB for active/trial tenants opted into content discovery and dispatches per-tenant jobs."""
    logger.info("🔍 Starting weekly keyword-driven content discovery dispatch.")
    dispatched_tenants: list[str] = []
    with ReadOnlySessionLocal() as db:
        try:
            opted_in_users = (
                db.query(User.id)
                .join(BusinessProfile, BusinessProfile.user_id == User.id)
                .filter(
                    User.is_active.is_(True),
                    User.subscription_status.in_(
                        [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]
                    ),
                    BusinessProfile.content_discovery_enabled.is_(True),
                )
                .all()
            )
            for (user_id,) in opted_in_users:
                tenant_id_str = str(user_id)
                discover_tenant_content.delay(tenant_id_str)
                dispatched_tenants.append(tenant_id_str)
            logger.info(
                "Dispatched content discovery for %d opted-in tenants.",
                len(dispatched_tenants),
            )
            return {
                "status": "success",
                "dispatched_count": len(dispatched_tenants),
                "tenants": dispatched_tenants,
            }
        except Exception as exc:
            logger.error("Failed to dispatch weekly content discovery: %s", exc)
            raise


@shared_task(name="src.tasks.marketing_advisor.discover_tenant_content")
def discover_tenant_content(tenant_id: str) -> dict[str, Any]:
    """
    Runs under least-privilege read-only RLS context: loads tenant Brand DNA and seen url_hashes,
    queries managed Search API, filters against anti-positioning, and hands vetted candidates
    to the mutations queue for persistence and owner notification.
    """
    try:
        parsed_uuid = uuid.UUID(str(tenant_id))
    except (ValueError, TypeError) as exc:
        logger.error("Invalid tenant_id format supplied to content discovery: %s", exc)
        return {"status": "error", "reason": "Invalid tenant UUID"}

    tenant_token = set_current_tenant_context(str(parsed_uuid))
    try:
        with ReadOnlySessionLocal() as db:
            tenant_user = db.query(User).filter(User.id == parsed_uuid).first()
            profile = (
                db.query(BusinessProfile).filter(BusinessProfile.user_id == parsed_uuid).first()
            )
            if not tenant_user or not profile:
                return {"status": "skipped", "reason": "Missing user or business profile"}

            brand = _build_brand_dna(tenant_user, profile)
            saved_keywords = (
                [str(k) for k in profile.search_keywords if k]
                if isinstance(profile.search_keywords, list)
                else []
            )
            generated_keywords: list[str] | None = None
            keywords_to_use = saved_keywords
            if not keywords_to_use:
                keywords_to_use = generate_search_keywords(brand, max_keywords=5)
                generated_keywords = keywords_to_use

            if not keywords_to_use:
                return {"status": "skipped", "reason": "No search keywords available"}

            existing_hashes = {
                row[0]
                for row in db.query(ContentSuggestion.url_hash)
                .filter(ContentSuggestion.user_id == parsed_uuid)
                .all()
                if row[0]
            }

            candidates = asyncio.run(
                discover_content_candidates(
                    brand=brand,
                    keywords=keywords_to_use,
                    existing_url_hashes=existing_hashes,
                )
            )
            serialized = [asdict(c) for c in candidates]
            if serialized or generated_keywords:
                persist_content_suggestions.delay(
                    str(parsed_uuid),
                    serialized,
                    generated_keywords,
                )
            return {
                "status": "discovered",
                "tenant_id": tenant_id,
                "candidates_found": len(serialized),
            }
    except Exception as exc:
        logger.error("Error discovering content for tenant %s: %s", tenant_id, exc)
        raise
    finally:
        reset_current_tenant_context(tenant_token)


@shared_task(name="src.tasks.marketing_advisor.persist_content_suggestions")
def persist_content_suggestions(
    tenant_id: str,
    candidates: list[dict[str, Any]],
    generated_keywords: list[str] | None = None,
) -> dict[str, Any]:
    """
    Runs on the mutations queue under write-permission RLS context:
    persists deduplicated PENDING ContentSuggestion rows, records AuditLog,
    and sends a WhatsApp approval preview to the business owner.
    """
    try:
        parsed_uuid = uuid.UUID(str(tenant_id))
    except (ValueError, TypeError) as exc:
        logger.error("Invalid tenant_id format supplied to persist_content_suggestions: %s", exc)
        return {"status": "error", "reason": "Invalid tenant UUID"}

    tenant_token = set_current_tenant_context(str(parsed_uuid))
    try:
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == parsed_uuid).first()
            if not user:
                return {"status": "error", "reason": "User not found"}

            if generated_keywords:
                profile = (
                    db.query(BusinessProfile).filter(BusinessProfile.user_id == parsed_uuid).first()
                )
                if profile and not profile.search_keywords:
                    profile.search_keywords = generated_keywords

            existing_hashes = {
                row[0]
                for row in db.query(ContentSuggestion.url_hash)
                .filter(ContentSuggestion.user_id == parsed_uuid)
                .all()
                if row[0]
            }

            created_items: list[ContentSuggestion] = []
            for item in candidates or []:
                url_hash = str(item.get("url_hash", "")).strip()
                if not url_hash or url_hash in existing_hashes:
                    continue
                suggestion = ContentSuggestion(
                    user_id=parsed_uuid,
                    title=sanitize_untrusted_text(str(item.get("title", "")), max_len=250)
                    or "רעיון לתוכן חדש",
                    source_url=str(item.get("url", ""))[:1000],
                    url_hash=url_hash[:64],
                    matched_keyword=sanitize_untrusted_text(
                        str(item.get("matched_keyword", "")), max_len=150
                    ),
                    source_provider=str(item.get("source_provider", "tavily"))[:50],
                    summary_he=sanitize_untrusted_text(
                        str(item.get("summary_he", "")), max_len=500
                    ),
                    draft_post_he=sanitize_untrusted_text(
                        str(item.get("draft_post_he", "")), max_len=1500
                    ),
                    relevance_reason=sanitize_untrusted_text(
                        str(item.get("relevance_reason", "")), max_len=300
                    ),
                    status="PENDING",
                )
                db.add(suggestion)
                existing_hashes.add(url_hash)
                created_items.append(suggestion)

            audit_entry = AuditLog(
                user_id=str(parsed_uuid),
                action="CONTENT_SUGGESTIONS_DISCOVERED",
                details={
                    "created_count": len(created_items),
                    "keywords_initialized": bool(generated_keywords),
                },
            )
            db.add(audit_entry)
            db.commit()

            if created_items and user.personal_whatsapp:
                preview_text = build_whatsapp_discovery_preview(
                    [(s.title, s.summary_he) for s in created_items]
                )
                whatsapp_adapter.send_message(
                    to_phone=user.personal_whatsapp,
                    text=preview_text,
                )

            return {
                "status": "persisted",
                "tenant_id": tenant_id,
                "created_count": len(created_items),
            }
    except Exception as exc:
        logger.error("Error persisting content suggestions for %s: %s", tenant_id, exc)
        raise
    finally:
        reset_current_tenant_context(tenant_token)
