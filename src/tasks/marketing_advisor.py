# src/tasks/marketing_advisor.py
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task

from src.database.models import (
    AuditLog,
    Lead,
    LeadStatus,
    MeetingSession,
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
from src.security.ai_guardrails import inspect_and_wrap_input
from src.services.ai.engine import ai_engine
from src.services.communication.whatsapp import whatsapp_adapter

logger = logging.getLogger("MarketingAdvisorTask")


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
    """Analyzes tenant lead metrics, top tags, meeting sessions, and stale leads under read-only RLS context."""
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
                inspect_and_wrap_input(s.summary or s.transcript or "").clean_text
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
            metrics = {
                "total_new_leads_7d": len(recent_leads),
                "status_breakdown": status_breakdown,
                "source_breakdown": source_breakdown,
                "tag_summary": tag_summary,
                "stale_leads_count": stale_leads_count,
                "session_summaries_sample": session_summaries[:3],
            }
            tenant_user = db.query(User).filter(User.id == parsed_uuid).first()
            business_name = tenant_user.business_name if tenant_user else "העסק שלך"
            prompt = f"You are the Virtual Chief Marketing Officer for '{business_name}'. Weekly Metrics: {metrics}. Task: Provide 3 concise, highly actionable marketing and conversion recommendations in professional Hebrew."
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
                digest_text = (
                    f"📊 סיכום שבועי עבור {business_name}:\n"
                    f"- סך הכל לידים חדשים השבוע: {len(recent_leads)}\n"
                    f"- לידים הדורשים מעקב חוזר: {stale_leads_count}\n"
                    "💡 המלצה: מומלץ לחזור ללידים החדשים בתוך שעתיים מרגע פנייתם להגדלת אחוזי ההמרה."
                )
            logger.info("Successfully analyzed marketing metrics for tenant %s", tenant_id)
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
