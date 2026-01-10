from celery import Celery
from faster_whisper import WhisperModel
from src.database.session import SessionLocal
from src.database.models import CoachingSession
from src.security.tenant import set_tenant_id

celery_app = Celery("worker", broker="redis://localhost:6379/0")

# Load model globally in worker memory (GPU/CPU)
# Using 'tiny' or 'base' for speed, 'large-v2' for accuracy
model = WhisperModel("medium", device="cpu", compute_type="int8")

@celery_app.task
def transcribe_session_task(session_id: str, tenant_id: str, file_path: str):
    """
    Background task to transcribe audio.
    Must manually set tenant context since it's outside the request loop.
    """
    # 1. Set context for security (if DB mixins are used)
    set_tenant_id(uuid.UUID(tenant_id))

    db = SessionLocal()
    try:
        # 2. Transcribe
        segments, _ = model.transcribe(file_path, beam_size=5)
        transcript = " ".join([segment.text for segment in segments])

        # 3. Save to DB (Encryption happens automatically via TypeDecorator)
        session_record = db.query(CoachingSession).filter(CoachingSession.id == session_id).first()
        if session_record:
            session_record.transcript_text = transcript
            # Trigger Summary Task here...
            db.commit()

    finally:
        db.close()
