# src/services/background_processor.py
import os
import logging
from sqlalchemy.orm import Session
from faster_whisper import WhisperModel

from src.database.session import SessionLocal
from src.database.models import CoachingSession, SessionStatus
from src.services.ai.engine import ai_engine

logger = logging.getLogger("BackgroundProcessor")

# Define the whisper model parameters for low-RAM (EC2 1GB)
# "tiny" model takes ~300MB RAM. compute_type="int8" reduces memory usage further.
MODEL_SIZE = "tiny" 

def process_audio_analysis(session_id: str, user_id: str, file_path: str):
    """
    Background task to transcribe a coaching session LOCALLY (for extreme privacy) 
    and then summarize the text via AI.
    """
    db = SessionLocal()
    session_record = db.query(CoachingSession).filter(CoachingSession.id == session_id).first()
    
    if not session_record:
        logger.error(f"Session {session_id} not found in DB.")
        db.close()
        return

    try:
        # Update status to PROCESSING
        session_record.status = SessionStatus.PROCESSING
        db.commit()

        logger.info(f"🎙️ Starting LOCAL transcription for session {session_id} using {MODEL_SIZE} model...")

        # --- 1. LOCAL TRANSCRIPTION (100% Private, No Audio sent to Cloud APIs) ---
        # Loading the model. It downloads it the first time it runs and caches it.
        # device="cpu" is required for standard EC2 instances without GPUs.
        model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        
        segments, info = model.transcribe(file_path, beam_size=5)
        
        logger.info(f"Detected language '{info.language}' with probability {info.language_probability}")

        # Stitch the transcription segments together
        full_transcript = []
        for segment in segments:
            full_transcript.append(segment.text)
        
        transcript_text = " ".join(full_transcript).strip()
        
        # --- 2. CLOUD SUMMARIZATION (Text Only) ---
        # Now that we have the text, we can safely send the TEXT to Gemini for summarization.
        logger.info(f"📝 Transcription complete. Generating summary via AI Engine...")
        summary_text = ai_engine.generate_meeting_summary(transcription_text=transcript_text)

        # --- 3. UPDATE DATABASE ---
        session_record.transcript = transcript_text
        session_record.summary = summary_text
        session_record.status = SessionStatus.COMPLETED
        db.commit()
        
        logger.info(f"✅ Session {session_id} processed successfully.")

    except Exception as e:
        logger.error(f"❌ Failed to process session {session_id}: {str(e)}")
        session_record.status = SessionStatus.FAILED
        db.commit()

    finally:
        db.close()
        
        # --- 4. PRIVACY ENFORCEMENT: Delete the audio file immediately ---
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"🗑️ Privacy enforcement: Deleted audio file {file_path}")
            except Exception as e:
                logger.error(f"⚠️ Could not delete audio file {file_path}: {str(e)}")