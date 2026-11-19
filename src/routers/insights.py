# src/routers/insights.py
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database.models import Lead, LeadStatus, User
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

        # TENANT ISOLATION: Explicitly filter by tenant_id (current_user.id)
        leads = (
            db.query(Lead)
            .filter(
                Lead.user_id == current_user.id,
                Lead.created_at >= six_months_ago,
            )
            .all()
        )

        total_leads = len(leads)
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

        qualified_leads = sum(
            1 for l in leads if l.status == LeadStatus.QUALIFIED or l.ai_rating == 1
        )
        conversion_rate = round((qualified_leads / total_leads) * 100, 1)

        # Aggregate lead summaries and common interest patterns
        service_mentions: dict[str, int] = {}
        for lead in leads:
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
