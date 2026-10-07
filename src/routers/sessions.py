# src/routers/sessions.py
import uuid
import os
import shutil
import logging
import magic # NEW: For Magic Bytes validation
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

# Database & Models
from src.database.session import get_db
from src.database.models import MeetingSession, Lead, User

# Security
from src.security.dependencies import get_current_user

# Config
from src.config import settings

# Services - Using Celery Worker instead of FastAPI BackgroundTasks
from src.tasks.audio_tasks import process_meeting_audio

router = APIRouter(tags=["Sessions"])
logger = logging.getLogger("SessionsRouter")

UPLOAD_DIR = "storage/audio"
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB Limit
ALLOWED_MIME_TYPES = {"audio/mpeg", "audio/mp4", "audio/ogg", "audio/wav", "audio/webm", "audio/x-m4a"}
MIME_EXTENSIONS = {
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "audio/x-m4a": ".m4a",
}

@router.post("/upload/{lead_id}")
async def upload_audio(
    lead_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads an audio file (recording) for a specific lead.
    The file is saved locally, and a background task is triggered for AI analysis.
    """
    
    # 1. Validate Lead Existence & Ownership
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.user_id == current_user.id,
    ).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # 2. Prepare Storage Path (User Isolated)
    # Structure: storage/audio/{user_id}/{filename}
    user_storage_path = os.path.join(UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_storage_path, exist_ok=True)

    # 3. Secure File Processing & Magic Bytes Validation
    # Read slightly more than MAX to detect overflow without loading a 1GB file into RAM
    file_bytes = await file.read(MAX_FILE_SIZE + 1)
    if len(file_bytes) > MAX_FILE_SIZE:
        logger.warning(f"SECURITY: User {current_user.email} attempted to upload a file exceeding 25MB.")
        raise HTTPException(status_code=413, detail="File too large. Max allowed size is 25MB.")

    mime_type = magic.from_buffer(file_bytes, mime=True)
    if mime_type not in ALLOWED_MIME_TYPES:
        logger.warning(f"SECURITY: User {current_user.email} uploaded blocked file type: {mime_type}")
        raise HTTPException(status_code=415, detail=f"Unsupported or malicious file type: {mime_type}")

    # 4. Save File to Disk
    file_ext = MIME_EXTENSIONS[mime_type]
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    full_path = os.path.join(user_storage_path, safe_filename)

    try:
        with open(full_path, "wb") as buffer:
            buffer.write(file_bytes)
    except Exception as e:
        logger.error(f"Failed to save audio file: {e}")
        raise HTTPException(status_code=500, detail="File save failed")

    # 5. Create Database Record (Domain Agnostic)
    new_session_id = str(uuid.uuid4())
    new_session = MeetingSession(
        id=new_session_id,
        lead_id=lead_id,
        user_id=current_user.id,
        audio_file_path=full_path,
        status="QUEUED"
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    # 6. Trigger Background Analysis via Celery Worker (Non-blocking, uses SWAP)
    logger.info(f"Queuing NLP analysis for Meeting {new_session_id}")
    process_meeting_audio.delay(
        session_id=new_session_id,
        user_id=str(current_user.id),
        file_path=full_path
    )

    return {
        "status": "queued",
        "session_id": new_session_id,
        "filename": safe_filename,
        "message": "Upload successful. Analysis started in background."
    }