import sys
import os
import time
import json
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# --- CRITICAL FIX: FORCE PATH TO ROOT ---
# Ensures the worker can find 'src' module when running from inside the container
sys.path.append('/app')

# --- PROJECT IMPORTS ---
from src.models.user import User
from src.models.lead import MediaInteraction, ProcessingStatus
from src.services.transcription import transcribe_audio
from src.services import ai_engine 

# --- CONFIGURATION ---
# Fetch Database URL from environment variables with a fallback
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@db:5432/leadflow")

# Fix for SQLAlchemy compatibility with modern PostgreSQL drivers
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- DATABASE SETUP ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_user_context(db, user_id):
    """
    Fetches business settings for a specific user.
    Ensures the AI tailors its response to the user's professional profile.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        return {
            "business_type": user.business_type or "General Business",
            "city_coverage": user.city_coverage
        }
    return {"business_type": "General Assistant", "city_coverage": None}

def process_jobs():
    """
    Main processing logic: Fetch pending jobs, transcribe audio, and analyze with AI.
    """
    db = SessionLocal()
    job = None
    
    try:
        # 1. Fetch a single pending job (Prioritize oldest)
        job = db.query(MediaInteraction).filter(
            MediaInteraction.status == ProcessingStatus.PENDING
        ).first()

        if not job:
            return False # No pending jobs found

        print(f"🎤 Processing Job {job.id} (Type: {job.media_type})")
        
        # 2. Lock job status to prevent duplicate processing
        job.status = ProcessingStatus.PROCESSING
        db.commit()

        text_for_ai = ""

        # --- STEP 1: Transcription (For Audio Files) ---
        if job.media_type == "AUDIO":
            try:
                # Ensure the path is absolute and exists
                file_path = job.file_path
                if not os.path.isabs(file_path):
                    file_path = os.path.join("/app", file_path)

                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Audio file not found at: {file_path}")

                print(f"   --> Transcribing: {file_path}")
                text_for_ai = transcribe_audio(file_path)
                
                # Save raw transcription to DB
                job.transcription_text = text_for_ai
                print(f"   ✅ Transcription: {text_for_ai[:50]}...")
            
            except Exception as e:
                print(f"   ❌ Transcription Failed: {e}")
                job.status = ProcessingStatus.FAILED
                job.ai_summary = f"Error during transcription: {str(e)}"
                db.commit()
                return True

        # --- STEP 2: Use message content directly (For Text Messages) ---
        elif job.media_type == "TEXT":
            text_for_ai = job.message_text or ""

        # --- STEP 3: AI Analysis (Gemini / LLM) ---
        if text_for_ai and len(text_for_ai) > 2:
            print(f"   --> Running AI Analysis...")
            
            # Retrieve user-specific business context
            context = get_user_context(db, job.user_id)
            
            # Analyze intent and generate summary/reply
            ai_result = ai_engine.analyze_lead_message(
                text=text_for_ai,
                business_type=context["business_type"],
                city_coverage=context["city_coverage"]
            )
            
            job.ai_summary = ai_result.get("summary")
            job.suggested_reply = ai_result.get("suggested_reply")
            print("   ✅ AI Analysis complete.")
        
        else:
            print("   ⚠ Skipping AI: No valid text content found.")
            job.ai_summary = "Incomplete data for analysis."

        # --- STEP 4: Finalize Job ---
        job.status = ProcessingStatus.COMPLETED
        db.commit()
        print(f"✨ Job {job.id} successfully finished.")
        return True

    except Exception as e:
        print(f"🔥 Critical Error in Worker: {e}")
        if job:
            job.status = ProcessingStatus.FAILED
            db.commit()
        return False
        
    finally:
        # Close DB connection to prevent memory leaks or connection exhaustion
        db.close()

if __name__ == "__main__":
    print("🚀 LeadFlow Worker started. Monitoring queue...")
    
    while True:
        try:
            # Attempt to process a job; if none, wait before checking again
            work_done = process_jobs()
            if not work_done:
                time.sleep(5) # Save CPU when idle
        except KeyboardInterrupt:
            print("🛑 Stopping Worker...")
            break
        except Exception as e:
            print(f"🌀 Unexpected loop error: {e}")
            time.sleep(10) # Cool down after crash