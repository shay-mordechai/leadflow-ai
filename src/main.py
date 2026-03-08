# src/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response  # <-- הוספנו כאן את Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import sentry_sdk

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# --- NEW: Centralized Rate Limiter (Fix for Circular Imports) ---
from src.security.rate_limiter import limiter

# --- NEW: Background Scheduler ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.tasks.billing_tasks import enforce_trial_expirations
from src.tasks.followup_tasks import process_smart_followups

# Database & Config
from src.config import settings
from src.database.session import engine, Base

# --- Router Imports ---
from src.routers import auth, leads, phones, sessions, facebook, settings as settings_router
from src.routers.billing import checkout, invoices
from src.routers.webhooks import twilio, meshulam, whatsapp

# --- Logging Setup (JSON Structured) ---
from pythonjsonlogger import jsonlogger

logger = logging.getLogger("LeadFlowSystem")
logger.setLevel(logging.INFO)

# Remove default handlers
if logger.handlers:
    logger.handlers.clear()

logHandler = logging.StreamHandler()
# This formats the log output as a clean JSON string
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s'
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

# --- Initialize Global Scheduler ---
scheduler = AsyncIOScheduler()

# --- Lifecycle Management (Graceful Shutdown Prep) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting System...")
    
    # 0. DATABASE AUTO-MIGRATION (Crucial for SQLite schema updates)
    logger.info("🗄️ Ensuring Database Schema is up to date...")
    Base.metadata.create_all(bind=engine)
    
    # 1. Start Background Jobs ONLY if not in testing mode
    if settings.APP_ENV != "testing":
        # Check for expired trials at midnight
        scheduler.add_job(enforce_trial_expirations, 'cron', hour=0, minute=0)
        
        # Send Smart Follow-ups daily at 10:00 AM
        scheduler.add_job(process_smart_followups, 'cron', hour=10, minute=0)
        
        scheduler.start()
        logger.info("📅 Background Task Scheduler started (Billing & Follow-up Jobs configured).")
    else:
        logger.info("📅 Running in testing mode - Scheduler disabled.")
    
    yield
    
    # 2. Tier 1 - Graceful Shutdown
    logger.info("🛑 Shutting down gracefully... Closing pending tasks and connections.")
    if settings.APP_ENV != "testing":
        scheduler.shutdown() # Wait for running jobs to finish
    engine.dispose() # Properly close database connection pool

# --- App Definition ---
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

app = FastAPI(title=settings.APP_NAME, version="3.0.0", lifespan=lifespan)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Tier 1 Security: Inject essential HTTP security headers to prevent XSS, 
    Clickjacking, and force HTTPS (HSTS).
    """
    response = await call_next(request)
    # Force browsers to use HTTPS only for the next year
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Prevent browsers from guessing the content type
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Prevent Clickjacking (framing the site inside an attacker's site)
    response.headers["X-Frame-Options"] = "DENY"
    # Enable browser's built-in XSS protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Basic Content Security Policy (allow self and standard data formats)
    response.headers["Content-Security-Policy"] = "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval';"
    
    return response
    
# --- Security: Register Rate Limiter ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Security: Global Exception Handler (Anti-Leak) ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Security: Catches internal errors and returns a generic 500.
    Explicitly forwards the exception to Sentry since we caught it.
    """
    if settings.SENTRY_DSN:
        sentry_sdk.capture_exception(exc)
        
    logger.error(f"Internal Server Error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error. Our team has been notified."}
    )

# --- Middleware ---
# 1. Trusted Host (Prevent Host Header Attacks)
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["my-leads.app", "*.my-leads.app", "localhost", "127.0.0.1"]
)

# --- NEW: Performance Middleware (Tier 2) ---
# Compresses responses larger than 500 bytes using Gzip. Reduces payload size by ~80%
app.add_middleware(GZipMiddleware, minimum_size=500)
# --------------------------------------------

# 2. CORS (Strict)
app.add_middleware(
    CORSMiddleware,
    # Security: Explicitly list allowed origins. Do NOT use "*" in production.
    allow_origins=[
        "https://my-leads.app",
        "https://www.my-leads.app",
        "http://localhost:3000" # For local dev
    ], 
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
app.include_router(facebook.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])

# Billing
app.include_router(checkout.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(invoices.router, prefix="/api/v1/billing", tags=["Billing"])

# Webhooks
app.include_router(twilio.router, prefix="/webhooks/twilio", tags=["Webhooks - Twilio"]) # https://my-leads.app/webhooks/twilio/sms
app.include_router(whatsapp.router, prefix="/webhooks/whatsapp", tags=["Webhooks - WhatsApp"])
app.include_router(meshulam.router, prefix="/webhooks/meshulam", tags=["Webhooks - Meshulam"])

# ==============================================================================
# 🏥 HEALTH CHECK
# ==============================================================================
@app.get("/health", tags=["System"])
@limiter.limit("5/minute") # Security: Prevent spamming health check
async def health_check(request: Request):
    return {
        "status": "online", 
        "version": "3.0.0",
        "mode": settings.APP_ENV
    }

# ==============================================================================
# 🛡️ DATA LOSS PREVENTION (DLP) TEST ROUTE
# ==============================================================================
@app.get("/test-leak", tags=["Security Testing"])
def test_leak(response: Response):
    # הגדרת ה-TTL הלוגי - זה אומר לפילטר: אל תוציא מידע רגיש החוצה!
    response.headers["X-Data-TTL"] = "1"

    # זה המידע שה-Backend מחזיר (כולל סודות שלקוח לא אמור לראות)
    data = {
        "status": "success",
        "user": {
            "username": "shay0129",
            "email": "shay@leadflow.app",
            "password": "my_super_secret_password", # סוד!
            "internal_token": "aws_token_xyz123"      # סוד!
        }
    }
    return data