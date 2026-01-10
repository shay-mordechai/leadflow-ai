# Professional English Comment:
# Celery worker tasks for background processing.
# Handles audio transcription using Faster-Whisper and summarization via OpenAI.
# Ensures Tenant Isolation is manually reconstructed for the async task.

import os
import openai
from celery import Celery
from faster_whisper import WhisperModel
from sqlalchemy.orm import Session
from src.database.session import SessionLocal
from src.database.models import Lead
from src.security.tenant import set_tenant_id
from src.config import settings
import uuid

# Initialize Celery
celery_app = Celery("tasks", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# Initialize Whisper Model (Loaded once per worker process)
# 'medium' model provides a good tradeoff for Hebrew accuracy vs speed
whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")

openai.api_key = settings.OPENAI_API_KEY

@celery_app.task
def process_audio_session(file_path: str, lead_id: str, tenant_id: str):
    """
    Orchestrates the audio-to-summary pipeline.
    1. Transcribes audio to text (Hebrew).
    2. Sends text to LLM for coaching summary.
    3. Updates the Lead record in the database.
    """
    # 1. Set Security Context (Critical for Multi-tenancy)
    set_tenant_id(uuid.UUID(tenant_id))

    db: Session = SessionLocal()

    try:
        # Step 2: Transcribe
        print(f"Starting transcription for {file_path}...")
        segments, info = whisper_model.transcribe(file_path, beam_size=5, language="he")

        transcript_text = " ".join([segment.text for segment in segments])
        print(f"--- TRANSCRIPT START ---\n{transcript_text}\n--- TRANSCRIPT END ---")
        
        if not transcript_text:
            print("Warning: Transcription resulted in empty text.")
            return

        # Step 3: Summarize via OpenAI
        print("Sending transcript to OpenAI...")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert NLP Coaching assistant. "
                        "Summarize the following Hebrew session transcript. "
                        "Include: Key Insights, Action Items, and Client Sentiment. "
                        "Output must be in Hebrew."
                    )
                },
                {"role": "user", "content": transcript_text}
            ],
            temperature=0.5
        )

        summary = response.choices[0].message.content

        # Step 4: Update Database
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.summary_text = summary
            # lead.last_transcript = transcript_text # Optional: if we want to store raw text
            db.commit()
            print(f"Successfully updated lead {lead_id} with summary.")

        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        print(f"Error processing session: {str(e)}")
        db.rollback()
    finally:
        db.close()
