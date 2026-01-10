# Professional English Comment:
# FastAPI Router for the Coach Dashboard (UI).
# Handles Server-Side Rendering (SSR) via Jinja2 and audio file uploads.

import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from src.database.session import get_db
from src.database.models import Lead, Tenant
from src.security.tenant import get_tenant_id
from src.worker.tasks import process_audio_session  # Imported from the new worker module

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")

# Simple dependency to simulate coach authentication
# In a real scenario, this would rely on cookies/session tokens
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    # Simulating a logged-in user by getting the first active tenant
    # In production, this must be replaced with proper Auth (OAuth2/JWT)
    tenant = db.query(Tenant).filter(Tenant.is_active == True).first()
    if not tenant:
        raise HTTPException(status_code=401, detail="No active tenant found")
    return tenant

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Tenant = Depends(get_current_user)
):
    """
    Renders the main dashboard.
    Fetches leads associated with the current tenant context.
    Note: 'phone_number' is automatically decrypted by the model when accessed.
    """
    # Verify context matches user (Sanity check)
    # The middleware in main.py should have already set the tenant context based on API Key or Session

    leads = Lead.get_query(db).order_by(Lead.created_at.desc()).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "coach_name": current_user.name,
        "leads": leads
    })

@router.post("/upload-session/{lead_id}")
async def upload_session(
    lead_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Handles audio file uploads for a specific lead.
    Saves the file locally and triggers the background Celery task.
    """
    tenant_id = get_tenant_id()

    # 1. Validate Lead exists for this tenant
    lead = Lead.get_query(db).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # 2. Save file temporarily
    upload_dir = f"uploads/{tenant_id}"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = f"{upload_dir}/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. Trigger Background Task
    # Passing IDs as strings to avoid serialization issues in Celery
    process_audio_session.delay(
        file_path=file_path,
        lead_id=str(lead_id),
        tenant_id=str(tenant_id)
    )

    return {"status": "processing_started", "filename": file.filename}
