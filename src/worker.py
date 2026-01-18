import sys
import os

# --- CRITICAL FIX: FORCE PATH TO ROOT ---
# This line tells Python to look for modules in the main /app folder
sys.path.append('/app')

import time
import json
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# --- IMPORTS ---
# Now these will work because we added /app to system path
from src.models.user import User
from src.models.lead import MediaInteraction, ProcessingStatus
from src.services.transcription import transcribe_audio
from src.services import ai_engine 

# --- CONFIGURATION ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@db:5432/leadflow")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- Database Setup ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

print("🚀 Worker Coordinator started. Waiting for jobs...")

print("🚀 Worker Coordinator started. Waiting for jobs...")

def get_user_context(db, user_id):
    """
    Fetches the business settings for the specific user.
    This ensures the AI acts as a specific professional (e.g., "Real Estate Agent").
    """
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
        # 1. Fetch one pending job (Audio or Text)
        job = db.query(MediaInteraction).filter(
            MediaInteraction.status == ProcessingStatus.PENDING
        ).first()

        if not job:
            return False # No work found

        print(f"🎤 Starting Job {job.id} (Type: {job.media_type})...")
        
        # Lock the job
        job.status = ProcessingStatus.PROCESSING
        db.commit()

        # Variable to hold the text we will send to Gemini
        text_for_ai = ""

        # --- STEP 1: Transcription (If Audio) ---
        if job.media_type == "AUDIO":
            try:
                if not job.file_path or not os.path.exists(job.file_path):
                    # Try to fix path if relative
                    if job.file_path and os.path.exists(os.path.join("/app", job.file_path)):
                         job.file_path = os.path.join("/app", job.file_path)
                    else:
                         raise FileNotFoundError(f"Audio file missing at: {job.file_path}")

                print(f"   --> Transcribing file: {job.file_path}")
                # Using the imported Whisper service
                text_for_ai = transcribe_audio(job.file_path)
                
                # Update DB with raw transcription
                job.transcription_text = text_for_ai
                print(f"   ✅ Transcription result: {text_for_ai[:50]}...")
            
            except Exception as e:
                print(f"   ❌ Transcription Failed: {e}")
                job.status = ProcessingStatus.FAILED
                job.ai_summary = f"Transcription Error: {str(e)}"
                db.commit()
                return True

        # If it was a text message (not audio), use the content directly
        elif job.media_type == "TEXT":
            text_for_ai = job.message_text or ""

        # --- STEP 2: AI Analysis (Gemini) ---
        # We only run AI if we have text (either from transcription or original message)
        if text_for_ai and len(text_for_ai) > 2:
            print(f"   --> Analyzing with Gemini...")
            
            # Fetch User Context (Business Type/City)
            context = get_user_context(db, job.user_id)
            
            # Call the AI Engine service
            ai_result = ai_engine.analyze_lead_message(
                text=text_for_ai,
                business_type=context["business_type"],
                city_coverage=context["city_coverage"]
            )
            
            # Map the JSON result back to the Database
            job.ai_summary = ai_result.get("summary")
            job.suggested_reply = ai_result.get("suggested_reply")
            
            # Optional: If you have columns for score/intent, save them too
            # job.intent_score = ai_result.get("intent_score")
            
            print("   ✅ AI Analysis complete.")
        
        else:
            print("   ⚠ No text content to analyze.")
            job.ai_summary = "No text detected."

        # --- STEP 3: Finalize ---
        job.status = ProcessingStatus.COMPLETED
        db.commit()
        print(f"✨ Job {job.id} Finished Successfully!")
        return True

    except Exception as e:
        print(f"🔥 Critical Worker Error: {e}")
        if job:
            job.status = ProcessingStatus.FAILED
            db.commit()
        return False
        
    finally:
        # Always close the DB connection to prevent leaks
        db.close()

if __name__ == "__main__":
    # Main Loop
    while True:
        try:
            had_work = process_jobs()
            if not had_work:
                # Sleep if no work to save CPU
                time.sleep(5)
        except KeyboardInterrupt:
            print("🛑 Worker stopping...")
            break
