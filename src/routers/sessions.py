# src/routers/sessions.py
import uuid
import os
import shutil
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session

# Database & Models
from src.database.session import get_db
from src.database.models import CoachingSession, Lead, User

# Security
from src.security.dependencies import get_current_user

# Config
from src.config import settings

# Services
# Ensure this service exists or create a placeholder for it
try:
    from src.services.background_processor import process_audio_analysis
except ImportError:
    # Fallback if service doesn't exist yet
    def process_audio_analysis(*args, **kwargs):
        logging.warning("Background processor not found. Audio analysis skipped.")

router = APIRouter(tags=["Sessions"])
logger = logging.getLogger("SessionsRouter")

UPLOAD_DIR = "storage/audio"

@router.post("/upload/{lead_id}")
async def upload_audio(
    lead_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads an audio file (recording) for a specific lead.
    The file is saved locally, and a background task is triggered for AI analysis.
    """
    
    # 1. Validate Lead Existence & Ownership
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Optional: Verify the lead belongs to the user
    if lead.owner_id != current_user.id:
        logger.warning(f"Unauthorized access attempt by User {current_user.id} on Lead {lead_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this lead")

    # 2. Prepare Storage Path (User Isolated)
    # Structure: storage/audio/{user_id}/{filename}
    user_storage_path = os.path.join(UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_storage_path, exist_ok=True)

    # 3. Save File to Disk
    file_ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    full_path = os.path.join(user_storage_path, safe_filename)

    try:
        with open(full_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save audio file: {e}")
        raise HTTPException(status_code=500, detail="File save failed")

    # 4. Create Database Record
    new_session_id = str(uuid.uuid4())
    new_session = CoachingSession(
        id=new_session_id,
        lead_id=lead_id,
        user_id=current_user.id, # Replaced tenant_id with user_id
        audio_file_path=full_path,
        status="queued"
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    # 5. Trigger Background Analysis (Non-blocking)
    logger.info(f"Queuing analysis for Session {new_session_id}")
    background_tasks.add_task(
        process_audio_analysis,
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