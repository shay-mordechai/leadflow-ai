# src/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import sentry_sdk

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# --- Security: Centralized Rate Limiter (Prevents Circular Imports) ---
from src.security.rate_limiter import limiter

# --- Tasks: Background Scheduler ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.tasks.billing_tasks import enforce_trial_expirations
from src.tasks.followup_tasks import process_smart_followups

# Database & Configuration
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

# Clear default handlers to avoid duplicate logs
if logger.handlers:
    logger.handlers.clear()

logHandler = logging.StreamHandler()
# Formats output as a structured JSON string for production observability
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s'
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

# --- Initialize Global Async Scheduler ---
scheduler = AsyncIOScheduler()

# --- Lifecycle Management (Startup/Shutdown Procedures) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting System...")
    
    # 0. Database Auto-Migration (Required for SQLite/PostgreSQL schema synchronization)
    logger.info("🗄️ Ensuring Database Schema is up to date...")
    Base.metadata.create_all(bind=engine)
    
    # 1. Background Job Registration (Disabled during testing)
    if settings.APP_ENV != "testing":
        # Cleanup expired trials daily at midnight
        scheduler.add_job(enforce_trial_expirations, 'cron', hour=0, minute=0)
        
        # Dispatch daily smart follow-ups at 10:00 AM
        scheduler.add_job(process_smart_followups, 'cron', hour=10, minute=0)
        
        scheduler.start()
        logger.info("📅 Background Task Scheduler started.")
    else:
        logger.info("📅 Testing mode detected - Scheduler disabled.")
    
    yield
    
    # 2. Graceful Shutdown (Engine cleanup and task termination)
    logger.info("🛑 Shutting down gracefully... Cleaning up resources.")
    if settings.APP_ENV != "testing":
        scheduler.shutdown()
    engine.dispose()

# --- Sentry Error Tracking ---
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
    """
    Tier 1 Security Middleware: Injects essential security headers 
    to mitigate XSS, Clickjacking, and enforce HSTS.
    """
    response = await call_next(request)
    # Enforce HTTPS-only communication
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Mitigate MIME-type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Prevent UI Redressing (Clickjacking)
    response.headers["X-Frame-Options"] = "DENY"
    # Enable browser-side XSS filtering
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Strict Content Security Policy
    response.headers["Content-Security-Policy"] = "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval';"
    
    return response

@app.middleware("http")
async def dlp_trigger_middleware(request: Request, call_next):
    """
    Tier 2 Security Middleware: Data Loss Prevention (DLP) Trigger.
    Automatically appends the 'X-Data-TTL' header to all API and Webhook responses.
    This header signals the Envoy WASM filter to scan the payload for sensitive data.
    """
    response = await call_next(request)
    
    # Target only specific API boundaries for DLP scanning to optimize performance
    path = request.url.path
    if path.startswith("/api/v1") or path.startswith("/webhooks") or path == "/test-leak":
        response.headers["X-Data-TTL"] = "1"
        
    return response
    
# --- Rate Limiting Configuration ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Anti-Leak Global Exception Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Prevents internal stack trace leakage. 
    Logs the error internally and returns a sanitized generic response.
    """
    if settings.SENTRY_DSN:
        sentry_sdk.capture_exception(exc)
        
    logger.error(f"Internal Server Error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error. Our team has been notified."}
    )

# --- General Middleware Stack ---

# 1. Trusted Host Middleware (Mitigates Host Header injection attacks)
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["my-leads.app", "*.my-leads.app", "localhost", "127.0.0.1"]
)

# 2. Compression Middleware (Improves performance by reducing payload size)
app.add_middleware(GZipMiddleware, minimum_size=500)

# 3. CORS Policy (Strict origin validation)
app.add_middleware(
    CORSMiddleware,
    # Security: Explicitly defined origins. Avoid using "*" in production environments.
    allow_origins=[
        "https://my-leads.app",
        "https://www.my-leads.app",
        "http://localhost:3000"
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

# Billing Subsystem
app.include_router(checkout.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(invoices.router, prefix="/api/v1/billing", tags=["Billing"])

# External Webhooks
app.include_router(twilio.router, prefix="/webhooks/twilio", tags=["Webhooks - Twilio"])
app.include_router(whatsapp.router, prefix="/webhooks/whatsapp", tags=["Webhooks - WhatsApp"])
app.include_router(meshulam.router, prefix="/webhooks/meshulam", tags=["Webhooks - Meshulam"])

# ==============================================================================
# 🏥 SYSTEM HEALTH CHECK
# ==============================================================================
@app.get("/health", tags=["System"])
@limiter.limit("5/minute")
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
    """
    Test endpoint designed to verify Envoy WASM Filter (DLP) functionality.
    The X-Data-TTL header triggers the filter to redact sensitive fields.
    """
    # Trigger Envoy WASM censorship logic (Now mostly handled by middleware, kept here for direct testing)
    response.headers["X-Data-TTL"] = "1"

    # Simulated response containing sensitive credentials
    data = {
        "status": "success",
        "user": {
            "username": "shay0129",
            "email": "shay@leadflow.app",
            "password": "my_super_secret_password", # Target for redaction
            "internal_token": "aws_token_xyz123"      # Target for redaction
        }
    }
    return data