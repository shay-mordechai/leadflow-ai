from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.orm import Session
import uuid
import os
import shutil
from src.database.session import get_db
from src.database.models import CoachingSession, Lead
from src.security.tenant import get_current_tenant_id, get_tenant_id
from src.worker.tasks import process_audio_session
from src.config import settings

router = APIRouter(tags=["Sessions"])

UPLOAD_DIR = "storage/audio"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def validate_file(file: UploadFile) -> bool:
    """
    Strict file validation:
    1. Check Size
    2. Check Magic Numbers (Header bytes)
    """
    # 1. Size Check
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large (Max 50MB)")

    # 2. Magic Number Check (Basic for Audio)
    # Read first 10 bytes
    header = await file.read(10)
    await file.seek(0)

    # Simple hex signatures for common audio (MP3, WAV, M4A)
    # ID3 (MP3), RIFF (WAV), ftyp (M4A)
    hex_head = header.hex()

    # This is a basic check. In production, use 'python-magic' library.
    is_valid = (
        header.startswith(b'ID3') or      # MP3
        header.startswith(b'\xff\xfb') or # MP3 No ID3
        header.startswith(b'RIFF') or     # WAV
        b'ftyp' in header                 # M4A/MP4
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid file format. Only audio allowed.")

    return True

@router.post("/upload/{lead_id}")
async def upload_audio(
    lead_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    # This dependency enforces that the request has a valid Tenant API Key
    tenant_id: str = Depends(get_current_tenant_id)
):
    # Validate Lead Ownership strictly within Tenant Scope
    # Note: Lead.get_query already filters by tenant_id from context
    lead = Lead.get_query(db).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Security Validations
    await validate_file(file)

    # Save File
    file_ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{uuid.uuid4()}{file_ext}"

    # Tenant isolation in storage structure
    tenant_storage_path = os.path.join(UPLOAD_DIR, tenant_id)
    os.makedirs(tenant_storage_path, exist_ok=True)

    full_path = os.path.join(tenant_storage_path, safe_filename)

    with open(full_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # DB Record
    new_session = CoachingSession(
        id=uuid.uuid4(),
        lead_id=lead_id,
        tenant_id=tenant_id, # Redundant but safe
        audio_file_path=full_path
    )
    db.add(new_session)
    db.commit()

    # Trigger Worker
    process_audio_session.delay(str(new_session.id))

    return {"status": "queued", "session_id": new_session.id}
