from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
import uuid
import os
import shutil
from src.database.session import get_db
from src.database.models import CoachingSession, Lead
from src.security.tenant import get_current_tenant_id
from src.services.background_processor import process_audio_analysis # New Service
from src.config import settings

router = APIRouter(tags=["Sessions"])
UPLOAD_DIR = "storage/audio"

@router.post("/upload/{lead_id}")
async def upload_audio(
    lead_id: str,
    background_tasks: BackgroundTasks, # FastAPI Injection
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    lead = Lead.get_query(db).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # 1. IO Bound: Save File
    file_ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    tenant_storage_path = os.path.join(UPLOAD_DIR, tenant_id)
    os.makedirs(tenant_storage_path, exist_ok=True)
    full_path = os.path.join(tenant_storage_path, safe_filename)

    with open(full_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. Database Record
    new_session = CoachingSession(
        id=uuid.uuid4(),
        lead_id=lead_id,
        tenant_id=tenant_id,
        audio_file_path=full_path,
        status="queued"
    )
    db.add(new_session)
    db.commit()

    # 3. Offload CPU intensive task to background thread pool
    # NO Celery required. Resilient and simple.
    background_tasks.add_task(
        process_audio_analysis,
        str(new_session.id),
        str(tenant_id),
        full_path
    )

    return {"status": "queued", "session_id": new_session.id}
