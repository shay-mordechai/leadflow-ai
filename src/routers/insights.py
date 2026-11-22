# src/routers/insights.py
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.models import KnowledgeDocument, Lead, LeadStatus, PendingApproval, User
from src.database.session import get_db
from src.security.dependencies import get_current_user

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

        # Generate Virtual CMO Recommendations
        recommendations = []
        if conversion_rate < 20:
            recommendations.append(
                "⚠️ אחוזי ההמרה שלך עומדים על פחות מ-20%. מומלץ לעדכן את הנחיות הבוט (System Instruction) להציע שיחת ייעוץ מהירה יותר לכל ליד נכנס."
            )
        else:
            recommendations.append(
                "✅ אחוזי ההמרה שלך מצוינים! כדאי לשקול להגדיל את תקציב הפרסום בקמפיינים המביאים את הלידים האיכותיים ביותר."
            )

        if service_mentions.get("שאלות מחיר ותקציב", 0) > (total_leads * 0.3):
            recommendations.append(
                "💡 מעל 30% מהלידים מעלים שאלות מחיר מוקדמות. מומלץ להוסיף שאלות סינון תקציב בטופס הנחיתה או לנסח מענה ממוקד ערך בבוט."
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
