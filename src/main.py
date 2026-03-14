# src/main.py
import logging
import traceback
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import sentry_sdk

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# --- Security: Centralized Rate Limiter ---
from src.security.rate_limiter import limiter

# --- Tasks: Background Scheduler ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.tasks.billing_tasks import enforce_trial_expirations
from src.tasks.followup_tasks import process_smart_followups

# Database & Configuration
from src.config import settings
from src.database.session import engine, Base

# --- Services ---
from src.services.communication.email import email_service # NEW: For error alerting

# --- Router Imports ---
from src.routers import auth, leads, phones, sessions, facebook, settings as settings_router
from src.routers import partners, system
from src.routers.billing import checkout, invoices
from src.routers.webhooks import twilio, meshulam, whatsapp

# --- Logging Setup (Global JSON Structured Logging) ---
from pythonjsonlogger import jsonlogger

def setup_json_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    log_handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
        rename_fields={"levelname": "level", "asctime": "timestamp"}
    )
    log_handler.setFormatter(formatter)
    root_logger.addHandler(log_handler)

    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = [log_handler]
        uvicorn_logger.propagate = False

setup_json_logging()
logger = logging.getLogger("LeadFlowSystem")
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting System...")
    logger.info("🗄️ Ensuring Database Schema is up to date...")
    Base.metadata.create_all(bind=engine)
    
    if settings.APP_ENV != "testing":
        scheduler.add_job(enforce_trial_expirations, 'cron', hour=0, minute=0)
        scheduler.add_job(process_smart_followups, 'cron', hour=10, minute=0)
        scheduler.start()
        logger.info("📅 Background Task Scheduler started.")
    
    yield
    
    logger.info("🛑 Shutting down gracefully... Cleaning up resources.")
    if settings.APP_ENV != "testing":
        scheduler.shutdown()
    engine.dispose()

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

app = FastAPI(title=settings.APP_NAME, version="3.0.0", lifespan=lifespan)

# ==============================================================================
# 🛡️ SECURITY MIDDLEWARE
# ==============================================================================

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval';"
    return response

@app.middleware("http")
async def dlp_trigger_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/v1") or path.startswith("/webhooks") or path == "/test-leak":
        response.headers["X-Data-TTL"] = "1"
    return response
    
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ==============================================================================
# 🚨 GLOBAL EXCEPTION HANDLER (THE AIRBAG)
# ==============================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Prevents internal stack trace leakage to the client. 
    1. Sends exact error to Sentry.
    2. Sends a detailed HTML email to the system administrator.
    3. Returns a clean, generic Hebrew error to the user.
    """
    if settings.SENTRY_DSN:
        sentry_sdk.capture_exception(exc)
        
    error_summary = str(exc)
    stack_trace = traceback.format_exc()
    logger.error(f"Internal Server Error: {error_summary}")

    # Safely extract context for the email report
    client_ip = request.client.host if request.client else "Unknown"
    request_info = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": client_ip
    }

    # Fire and Forget: Send email in the background so the user doesn't wait
    asyncio.create_task(email_service.send_error_alert_email(
        error_summary=error_summary, 
        stack_trace=stack_trace, 
        request_info=request_info
    ))

    # Return a friendly, localized message to the user
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "אופס! משהו השתבש בצד שלנו. הצוות הטכני קיבל דיווח ויטפל בזה בהקדם."}
    )

# --- General Middleware Stack ---
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["my-leads.app", "*.my-leads.app", "localhost", "127.0.0.1"])
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://my-leads.app", "https://www.my-leads.app", "http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ==============================================================================
# 🔗 ROUTER REGISTRATION
# ==============================================================================
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["Leads"])
app.include_router(phones.router, prefix="/api/v1/phones", tags=["Phones"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(facebook.router, prefix="/api/v1")
app.include_router(partners.router) 

app.include_router(checkout.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(invoices.router, prefix="/api/v1/billing", tags=["Billing"])

app.include_router(twilio.router, prefix="/webhooks/twilio", tags=["Webhooks - Twilio"])
app.include_router(whatsapp.router, prefix="/webhooks/whatsapp", tags=["Webhooks - WhatsApp"])
app.include_router(meshulam.router, prefix="/webhooks/meshulam", tags=["Webhooks - Meshulam"])

app.include_router(system.router)

# ==============================================================================
# 🏥 SYSTEM HEALTH CHECK
# ==============================================================================
@app.get("/health", tags=["System"])
@limiter.limit("5/minute")
async def health_check(request: Request):
    return {"status": "online", "version": "3.0.0", "mode": settings.APP_ENV}

@app.get("/test-leak", tags=["Security Testing"])
def test_leak(response: Response):
    response.headers["X-Data-TTL"] = "1"
    data = {
        "status": "success",
        "user": {
            "username": "shay0129",
            "email": "shay@leadflow.app",
            "password": "my_super_secret_password",
            "internal_token": "aws_token_xyz123" 
        }
    }
    return data