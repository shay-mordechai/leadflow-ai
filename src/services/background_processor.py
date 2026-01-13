import os
import time
import logging
from sqlalchemy.orm import Session
from src.database.session import SessionLocal
from src.database.models import Lead, CoachingSession, Tenant
from src.services.ai_engine import ai_engine

# Professional English Comment:
# Importing faster_whisper for optimized local inference.
# This library is 4x faster than standard whisper and uses less RAM.
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("CRITICAL: faster-whisper not installed.")
    WhisperModel = None

logger = logging.getLogger(__name__)

# Global model instance (Lazy loading pattern could be applied here if RAM is critical)
# 'small' model is the best balance for Hebrew on CPU. 'medium' might crash a t3.micro.
# compute_type="int8" reduces memory usage by 50% with minimal accuracy loss.
MODEL_SIZE = "small"
_model_instance = None

def get_whisper_model():
    """
    Singleton pattern to load the model only once.
    """
    global _model_instance
    if _model_instance is None:
        logger.info(f"Loading Whisper Model ({MODEL_SIZE}) on CPU...")
        try:
            _model_instance = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
            logger.info("Whisper Model loaded successfully.")
        except Exception as e:
            logger.critical(f"Failed to load Whisper Model: {e}")
            raise e
    return _model_instance

def cleanup_old_files(file_path: str):
    """
    Security & Cleanup: Removes the audio file after processing to save disk space.
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted processed file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to delete file {file_path}: {e}")

def process_audio_analysis(session_id: str, tenant_id: str, file_path: str):
    """
    Main Background Task:
    1. Transcribes audio locally using Whisper (CPU).
    2. Analyzes text using LLM (External API).
    3. Updates DB.
    """
    db = SessionLocal()
    session = db.query(CoachingSession).filter(CoachingSession.id == session_id).first()

    if not session:
        logger.error(f"Session {session_id} not found in DB.")
        db.close()
        return

    try:
        logger.info(f"Starting local transcription for Session: {session_id}")

        # --- Step 1: Local Transcription (Zero Cost) ---
        model = get_whisper_model()

        # beam_size=5 gives better accuracy for Hebrew.
        segments, info = model.transcribe(file_path, beam_size=5, language="he")

        # Collect all text segments
        transcript_text = " ".join([segment.text for segment in segments])

        if not transcript_text:
            logger.warning(f"Whisper returned empty text for {session_id}")
            transcript_text = "[לא זוהה דיבור]"

        # Update DB with transcript immediately
        session.transcript = transcript_text
        session.status = "transcribed"
        db.commit()

        logger.info(f"Transcription complete. Length: {len(transcript_text)} chars.")

        # --- Step 2: AI Analysis (Low Cost - Text only) ---
        # We now send only TEXT to the LLM, which is very cheap compared to Audio.

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        business_type = tenant.business_type if tenant else "General"

        # Call the existing AI Engine (Make sure it takes 'text' input)
        analysis = ai_engine.analyze_lead_message(
            transcript_text,
            business_type,
            tenant.city_coverage
        )

        # Update Session with Insights
        session.summary = analysis.get("summary", "Analysis unavailable")
        session.status = "completed"

        # Update Lead Status if needed
        if session.lead_id:
            lead = db.query(Lead).filter(Lead.id == session.lead_id).first()
            if lead:
                lead.summary_text = analysis.get("summary")
                if analysis.get("intent_score", 0) >= 8:
                    lead.status = "QUALIFIED"

        db.commit()
        logger.info(f"Session {session_id} processing finished successfully.")

    except Exception as e:
        logger.error(f"CRITICAL FAILURE in Session {session_id}: {str(e)}")
        session.status = "failed"
        session.summary = f"System Error: {str(e)}"
        db.commit()

    finally:
        # --- Step 3: Cleanup ---
        cleanup_old_files(file_path)
        db.close()
