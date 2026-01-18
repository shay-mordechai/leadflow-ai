import sys
import os
import time
import json
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# --- CRITICAL FIX: FORCE PATH TO ROOT ---
sys.path.append('/app')

# --- CORRECTED IMPORTS ---
# This fixes the ModuleNotFoundError by pointing to the correct location
try:
    from src.database.models import User, MediaInteraction, ProcessingStatus
except ImportError:
    print("⚠ Standard import failed. Using fallback...")
    from src.database.models import User, MediaInteraction
    class ProcessingStatus:
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

from src.services.transcription import transcribe_audio
from src.services import ai_engine 

# --- CONFIGURATION ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@db:5432/leadflow")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- DATABASE SETUP ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_user_context(db, user_id):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        return {
            "business_type": user.business_type or "General Business",
            "city_coverage": user.city_coverage
        }
    return {"business_type": "General Assistant", "city_coverage": None}

def process_jobs():
    db = SessionLocal()
    job = None
    try:
        job = db.query(MediaInteraction).filter(
            MediaInteraction.status == ProcessingStatus.PENDING
        ).first()

        if not job:
            return False 

        print(f"🎤 Processing Job {job.id} (Type: {job.media_type})")
        job.status = ProcessingStatus.PROCESSING
        db.commit()

        text_for_ai = ""

        if job.media_type == "AUDIO":
            try:
                file_path = job.file_path
                if not os.path.isabs(file_path):
                    file_path = os.path.join("/app", file_path)
                
                # Fallback check
                if not os.path.exists(file_path):
                     base_name = os.path.basename(file_path)
                     alt_path = os.path.join("/app/storage", base_name)
                     if os.path.exists(alt_path):
                         file_path = alt_path

                print(f"   --> Transcribing: {file_path}")
                text_for_ai = transcribe_audio(file_path)
                job.transcription_text = text_for_ai
            except Exception as e:
                print(f"   ❌ Transcription Error: {e}")
                job.status = ProcessingStatus.FAILED
                job.ai_summary = f"Error: {e}"
                db.commit()
                return True

        elif job.media_type == "TEXT":
            text_for_ai = job.message_text or ""

        if text_for_ai and len(text_for_ai) > 1:
            print(f"   --> AI Analysis...")
            context = get_user_context(db, job.user_id)
            try:
                ai_result = ai_engine.analyze_lead_message(
                    text=text_for_ai,
                    business_type=context["business_type"],
                    city_coverage=context["city_coverage"]
                )
                job.ai_summary = ai_result.get("summary")
                job.suggested_reply = ai_result.get("suggested_reply")
                print("   ✅ AI Done.")
            except Exception as e:
                print(f"   ⚠ AI Error (Gemini missing?): {e}")
                job.ai_summary = "AI Analysis Failed"
        
        job.status = ProcessingStatus.COMPLETED
        db.commit()
        return True

    except Exception as e:
        print(f"🔥 Job Loop Error: {e}")
        if job:
            job.status = ProcessingStatus.FAILED
            db.commit()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Worker Started (v2 - Fixed Imports).")
    while True:
        try:
            if not process_jobs():
                time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"CRITICAL: {e}")
            time.sleep(10)
