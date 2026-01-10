# src/main.py

from fastapi import FastAPI, Request, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_
import uuid
import csv
import io
from datetime import datetime, timedelta

# Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Database & Config
from src.config import settings
from src.routers import leads, sessions
from src.database.session import engine, get_db
from src.database.models import Base, Tenant, Lead, TimeSlot
from src.security.hashing import get_hash
from pydantic import BaseModel

# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_Global])

app = FastAPI(title=settings.APP_NAME, version="2.2.0-FEATURES")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Middlewares ---
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(CORSMiddleware, allow_origins=settings.ALLOWED_HOSTS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

# --- Setup ---
app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

# --- UI Routes ---

@app.get("/")
async def read_marketing_page(request: Request):
    return templates.TemplateResponse("marketing.html", {"request": request})

@app.get("/register")
async def read_register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/payment")
async def read_payment_page(request: Request):
    return templates.TemplateResponse("payment.html", {"request": request})

@app.get("/login")
async def login_page(request: Request):
    # In a real app, this would verify credentials
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard")
async def read_dashboard(request: Request, db: Session = Depends(get_db)):
    # In production, get current tenant from session/cookie
    tenant = db.query(Tenant).first() # Demo mode

    if not tenant:
        return RedirectResponse("/register")

    leads_data = db.query(Lead).filter(Lead.tenant_id == tenant.id).order_by(Lead.created_at.desc()).all()

    total = len(leads_data)
    qualified = sum(1 for l in leads_data if l.status == "QUALIFIED" or (l.coach_feedback and "8" in l.coach_feedback))

    # Task 2: Calculate Follow-ups for today
    today_followups = sum(1 for l in leads_data if l.needs_followup)

    stats = {
        "total": total,
        "qualified": qualified,
        "followups": today_followups,
        "conv_rate": f"{(qualified/total*100):.1f}%" if total > 0 else "0%"
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "leads": leads_data,
        "coach_name": tenant.name,
        "tenant_id": tenant.id,
        "stats": stats
    })

# --- Task 3: CSV Export Endpoint ---
@app.get("/api/v1/leads/export")
async def export_leads(db: Session = Depends(get_db)):
    tenant = db.query(Tenant).first() # Demo: assume logged in
    leads_data = db.query(Lead).filter(Lead.tenant_id == tenant.id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Phone", "City", "Status", "Summary", "Date"])

    for lead in leads_data:
        writer.writerow([
            lead.name,
            lead.phone_number,
            lead.city,
            lead.status,
            lead.summary_text,
            lead.created_at.strftime("%Y-%m-%d")
        ])

    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=leads_export.csv"
    return response

# --- Task 4: Smart Calendar System ---

@app.get("/schedule")
async def read_schedule(request: Request, db: Session = Depends(get_db)):
    """ Coach View: Manage availability """
    tenant = db.query(Tenant).first() # Demo context

    # Get all slots for next 14 days
    start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=14)

    existing_slots = db.query(TimeSlot).filter(
        TimeSlot.tenant_id == tenant.id,
        TimeSlot.start_time >= start_date,
        TimeSlot.start_time <= end_date
    ).all()

    # Convert to set for easy lookup
    active_slots = {slot.start_time.strftime("%Y-%m-%d %H:%M") for slot in existing_slots}

    return templates.TemplateResponse("schedule.html", {
        "request": request,
        "tenant_id": tenant.id,
        "active_slots": active_slots # Pass to JS
    })

class ToggleSlotRequest(BaseModel):
    date_str: str # YYYY-MM-DD
    time_str: str # HH:MM

@app.post("/api/v1/schedule/toggle")
async def toggle_slot(data: ToggleSlotRequest, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).first()

    # Parse DateTime
    try:
        dt_str = f"{data.date_str} {data.time_str}"
        slot_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Date/Time format")

    # Check if exists
    existing = db.query(TimeSlot).filter(
        TimeSlot.tenant_id == tenant.id,
        TimeSlot.start_time == slot_dt
    ).first()

    if existing:
        if existing.is_booked:
             raise HTTPException(status_code=400, detail="Cannot remove a booked slot")
        db.delete(existing)
        action = "removed"
    else:
        new_slot = TimeSlot(tenant_id=tenant.id, start_time=slot_dt, is_booked=False)
        db.add(new_slot)
        action = "added"

    db.commit()
    return {"status": "success", "action": action}

# Public Booking Page (Simplification for Demo)
@app.get("/book/{tenant_id}")
async def public_booking_page(tenant_id: str, request: Request, db: Session = Depends(get_db)):
    # In a real app, this would be a separate template.
    # Reusing schedule.html in 'read-only' mode for brevity or JSON for a frontend.
    # Fetch available slots
    slots = db.query(TimeSlot).filter(
        TimeSlot.tenant_id == uuid.UUID(tenant_id),
        TimeSlot.is_booked == False,
        TimeSlot.start_time > datetime.utcnow()
    ).all()

    return {"available_slots": [s.start_time for s in slots]}


# --- Registration & Models ---
class RegisterRequest(BaseModel):
    name: str
    personal_whatsapp: str
    business_whatsapp: str = ""
    needs_new_number: bool = False
    business_type: str
    city_coverage: str

@app.post("/api/v1/auth/register")
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register_coach(data: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    final_number = f"PENDING_{uuid.uuid4().hex[:8]}" if data.needs_new_number else data.business_whatsapp

    new_tenant = Tenant(
        id=uuid.uuid4(),
        name=data.name,
        personal_whatsapp=data.personal_whatsapp,
        whatsapp_number=final_number,
        requires_new_number=data.needs_new_number,
        business_type=data.business_type,
        city_coverage=data.city_coverage,
        api_key_hash=get_hash(str(uuid.uuid4())),
        is_active=True
    )
    db.add(new_tenant)
    db.commit()
    return {"status": "success"}

app.include_router(leads.router, prefix="/api/v1/leads")
app.include_router(sessions.router, prefix="/api/v1/sessions")

@app.on_event("startup")
def startup_event():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
