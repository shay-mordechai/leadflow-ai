# src/worker.py
import sys
import os
import time
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- CRITICAL FIX: FORCE PATH TO ROOT ---
# Ensures Python can find the 'src' module when running inside Docker
sys.path.append('/app')

from src.config import settings
from src.database.session import SessionLocal
from src.database.models import User, MediaInteraction, ProcessingStatus, BusinessProfile
from src.services.media.transcription import transcriber # Assuming you moved transcription here
from src.services.ai.engine import ai_engine

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Worker")

def get_user_context(db, user_id):
    """
    Fetches business context for the AI.
    """
    user = db.query(User).filter(User.id == user_id).first()
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == user_id).first()
    
    if user:
        return {
            "name": user.name,
            "business_type": user.business_type or "General Business",
            "business_name": user.business_name or "My Business",
            "location": user.last_known_city or "Israel"
        }
    return {}

def process_jobs():
    """
    Main polling loop. Fetches PENDING jobs and processes them.
    """
    db = SessionLocal()
    job = None
    try:
        # Fetch a pending job
        job = db.query(MediaInteraction).filter(
            MediaInteraction.status == ProcessingStatus.PENDING
        ).first()

        if not job:
            return False 

        logger.info(f"🎤 Processing Job {job.id} (Type: {job.media_type})")
        job.status = ProcessingStatus.PROCESSING
        db.commit()

        text_for_ai = ""

        # --- STEP 1: TRANSCRIPTION ---
        if job.media_type == "AUDIO":
            try:
                file_path = job.file_path
                # Ensure absolute path for Docker
                if not os.path.isabs(file_path):
                    file_path = os.path.join("/app", file_path)
                
                # Fallback check for file existence
                if not os.path.exists(file_path):
                     base_name = os.path.basename(file_path)
                     alt_path = os.path.join("/app/storage", base_name)
                     if os.path.exists(alt_path):
                         file_path = alt_path

                logger.info(f"   --> Transcribing: {file_path}")
                # Using the transcription service
                trans_result = transcriber.transcribe_audio(file_path)
                text_for_ai = trans_result.get("text", "")
                
                job.transcription_text = text_for_ai
            except Exception as e:
                logger.error(f"   ❌ Transcription Error: {e}")
                job.status = ProcessingStatus.FAILED
                job.ai_summary = f"Error: {e}"
                db.commit()
                return True

        elif job.media_type == "TEXT":
            text_for_ai = job.message_text or ""

        # --- STEP 2: AI ANALYSIS ---
        if text_for_ai and len(text_for_ai) > 1:
            logger.info(f"   --> AI Analysis...")
            context = get_user_context(db, job.user_id)
            
            try:
                # We use the generic raw analysis from the engine
                # Note: In a synchronous worker, we call the synchronous method or run async wrapper
                # Here we construct a prompt manually to use generate_raw_analysis
                
                system_prompt = f"""
                Role: Business Assistant for {context.get('business_name')}.
                Context: {context.get('business_type')}.
                Task: Analyze the following message: "{text_for_ai}".
                Output JSON: {{ "summary": "Hebrew summary", "suggested_reply": "Hebrew reply", "intent": "string" }}
                """
                
                ai_result = ai_engine.generate_raw_analysis(prompt=system_prompt)
                
                job.ai_summary = ai_result.get("summary")
                job.suggested_reply = ai_result.get("suggested_reply")
                logger.info("   ✅ AI Done.")
            except Exception as e:
                logger.error(f"   ⚠ AI Error: {e}")
                job.ai_summary = "AI Analysis Failed"
        
        job.status = ProcessingStatus.COMPLETED
        db.commit()
        return True

    except Exception as e:
        logger.error(f"🔥 Job Loop Error: {e}")
        if job:
            job.status = ProcessingStatus.FAILED
            db.commit()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Worker Started (v2.1).")
    while True:
        try:
            if not process_jobs():
                time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.critical(f"CRITICAL WORKER FAILURE: {e}")
            time.sleep(10)