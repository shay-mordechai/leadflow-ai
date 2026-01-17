# src/worker.py
import time
import os
import sys
from faster_whisper import WhisperModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.models import MediaInteraction, ProcessingStatus
from src.database.session import DATABASE_URL

# Setup separate DB connection for the worker
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

MODEL_SIZE = "tiny" # Use "small" or "base" if RAM permits
DEVICE = "cpu"
COMPUTE_TYPE = "int8" # Crucial for low RAM usage

print(f"🚀 Worker starting... Loading Whisper model ({MODEL_SIZE})...")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print("✅ Model loaded. Waiting for jobs...")

def process_jobs():
    db = SessionLocal()
    try:
        # Fetch one pending job
        job = db.query(MediaInteraction).filter(
            MediaInteraction.status == ProcessingStatus.PENDING,
            MediaInteraction.media_type == "AUDIO"
        ).first()

        if not job:
            return False # No work found

        print(f"🎤 Found job: {job.id}. Transcribing...")
        
        # Lock job
        job.status = ProcessingStatus.PROCESSING
        db.commit()

        # Check file existence
        if not os.path.exists(job.file_path):
            print(f"❌ File not found: {job.file_path}")
            job.status = ProcessingStatus.FAILED
            job.transcription_text = "Error: File not found on server storage."
            db.commit()
            return True

        # Transcribe
        segments, _ = model.transcribe(job.file_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])

        # Update DB
        job.transcription_text = text.strip()
        job.status = ProcessingStatus.COMPLETED
        db.commit()
        
        print(f"✅ Job {job.id} completed! Length: {len(text)} chars.")
        return True

    except Exception as e:
        print(f"🔥 Error processing job: {e}")
        if job:
            job.status = ProcessingStatus.FAILED
            db.commit()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    while True:
        try:
            had_work = process_jobs()
            if not had_work:
                time.sleep(5) # Sleep if no work to save CPU
        except KeyboardInterrupt:
            print("🛑 Worker stopping...")
            break