# src/worker/tasks.py

from celery import Celery
import os
from src.database.session import SessionLocal
from src.database.models import CoachingSession, Lead, Tenant
from src.services.ai_engine import ai_engine
from src.security.tenant import set_tenant_id, reset_tenant_id
from src.config import settings

# Initialize Celery app
celery_app = Celery("tasks", broker=settings.REDIS_URL)

@celery_app.task(name="analyze_lead_async")
def analyze_lead_async(lead_id: str, tenant_id: str, raw_text: str):
    """
    Professional English Comment:
    Background task to analyze a lead's raw text using Gemini.
    Handles Multi-tenant security context switching.
    """
    # 1. Set Security Context
    token = set_tenant_id(str(tenant_id))

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        lead = db.query(Lead).filter(Lead.id == lead_id).first()

        if not tenant or not lead:
            return "Error: Tenant or Lead not found"

        # 2. AI Analysis (Using Gemini via AI Engine)
        analysis_result = ai_engine.analyze_lead_message(
            text=raw_text,
            business_type=tenant.business_type or "General Service",
            city_coverage=tenant.city_coverage
        )

        # 3. Update Database
        lead.name = analysis_result.get("lead_name") or lead.name
        lead.city = analysis_result.get("location")
        lead.summary_text = analysis_result.get("summary")
        lead.coach_feedback = f"AI Score: {analysis_result.get('intent_score')}/10"

        if analysis_result.get("intent_score", 0) >= 7:
            lead.status = "QUALIFIED"

        db.commit()
        return f"Lead {lead_id} analyzed successfully."

    except Exception as e:
        db.rollback()
        return f"Task Failed: {str(e)}"
    finally:
        db.close()
        # Cleanup Security Context
        reset_tenant_id(token)

@celery_app.task(name="src.worker.tasks.process_audio_session")
def process_audio_session(session_id: str):
    """
    Legacy support: Transcribes audio (currently placeholder/mock without OpenAI)
    and extracts city using Gemini.
    """
    db = SessionLocal()
    try:
        session = db.query(CoachingSession).filter(CoachingSession.id == session_id).first()
        if not session: return "Session not found"

        tenant = db.query(Tenant).filter(Tenant.id == session.tenant_id).first()

        # NOTE: For real transcription without OpenAI, we would use a local Whisper model here.
        # For now, we assume transcript exists or we skip this step.
        transcript_text = "Transcription placeholder"

        # Extract City using Gemini
        # We reuse the AI engine logic but just ask for location
        analysis = ai_engine.analyze_lead_message(
            text=transcript_text,
            business_type=tenant.business_type if tenant else "General",
            city_coverage=tenant.city_coverage if tenant else None
        )

        detected_city = analysis.get("location", "Unknown")

        # Save results
        session.transcript = transcript_text
        session.status = "completed"
        db.commit()

        return f"Session {session_id} processed. City: {detected_city}"

    except Exception as e:
        db.rollback()
        return f"Error: {str(e)}"
    finally:
        db.close()
