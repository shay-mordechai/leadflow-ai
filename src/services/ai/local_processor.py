# src/services/ai/local_processor.py
import os
import logging
from sqlalchemy.orm import Session
from src.database.session import SessionLocal
# Note: Ensure CoachingSession and Tenant are defined in your models.py
# If they are not, you might want to map this to 'MediaInteraction' instead.
from src.database.models import Lead, CoachingSession, Tenant
from src.services.ai.engine import ai_engine

# Professional English Comment:
# Importing faster_whisper for optimized local inference.
# This library is 4x faster than standard whisper and uses significantly less RAM.
# Ideal for T3.Micro/Small instances.
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("CRITICAL: faster-whisper not installed. Local transcription will fail.")
    WhisperModel = None

logger = logging.getLogger("Local_Audio_Processor")

# Global model instance settings
# 'small' is the best balance for Hebrew on CPU. 
# 'int8' quantization reduces memory usage by ~50% with minimal accuracy loss.
MODEL_SIZE = "small"
_model_instance = None

def get_whisper_model():
    """
    Singleton pattern to load the Whisper model only once.
    Lazy loading prevents memory consumption until the first actual request.
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
    Security & Cleanup: Removes the audio file after processing to save disk space
    and ensure data privacy (GDPR compliance).
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
    1. Transcribes audio locally using Whisper (CPU) - Zero API Cost.
    2. Sends ONLY the text to the AI Engine (LLM) - Low API Cost.
    3. Updates the Database with insights.
    """
    db = SessionLocal()
    
    try:
        # Fetch Session Data
        session = db.query(CoachingSession).filter(CoachingSession.id == session_id).first()
        if not session:
            logger.error(f"Session {session_id} not found in DB.")
            return

        logger.info(f"Starting local transcription for Session: {session_id}")

        # --- Step 1: Local Transcription (Whisper) ---
        model = get_whisper_model()

        # beam_size=5 provides better accuracy for complex languages like Hebrew
        segments, info = model.transcribe(file_path, beam_size=5, language="he")

        # Combine segments into a single string
        transcript_text = " ".join([segment.text for segment in segments])

        if not transcript_text:
            logger.warning(f"Whisper returned empty text for {session_id}")
            transcript_text = "[No speech detected]"

        # Save Transcript immediately
        session.transcript = transcript_text
        session.status = "transcribed"
        db.commit()

        logger.info(f"Transcription complete. Length: {len(transcript_text)} chars.")

        # --- Step 2: AI Analysis (Via Central Engine) ---
        # Fetch Tenant context for better AI accuracy
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        business_type = tenant.business_type if tenant else "General"
        location = getattr(tenant, "city_coverage", "Israel")

        # Construct a specific prompt for the Engine
        system_prompt = f"""
        Role: AI Business Analyst for a '{business_type}' business in {location}.
        
        Task: Analyze the following transcribed text from a coaching/sales session.
        
        Transcript:
        "{transcript_text}"
        
        Output Requirement (JSON):
        {{
            "summary": "Concise summary in Hebrew",
            "intent_score": 1-10 (int),
            "key_insights": ["point 1", "point 2"],
            "suggested_action": "Follow up / Close deal / None"
        }}
        """

        # Call the generic method in ai_engine (Text-only mode)
        analysis = ai_engine.generate_raw_analysis(prompt=system_prompt)

        # --- Step 3: Save Insights ---
        session.summary = analysis.get("summary", "Analysis unavailable")
        session.status = "completed"

        # Optional: Update related Lead if high intent detected
        if session.lead_id:
            lead = db.query(Lead).filter(Lead.id == session.lead_id).first()
            if lead:
                lead.transcription_summary = analysis.get("summary")
                # If intent score is high (8+), mark lead as Qualified
                if isinstance(analysis.get("intent_score"), int) and analysis.get("intent_score") >= 8:
                    lead.status = "QUALIFIED"

        db.commit()
        logger.info(f"Session {session_id} processing finished successfully.")

    except Exception as e:
        logger.error(f"CRITICAL FAILURE in Session {session_id}: {str(e)}")
        # Attempt to update status to failed so UI knows
        try:
            session.status = "failed"
            session.summary = f"System Error: {str(e)}"
            db.commit()
        except:
            db.rollback()

    finally:
        # --- Step 4: Cleanup ---
        cleanup_old_files(file_path)
        db.close()