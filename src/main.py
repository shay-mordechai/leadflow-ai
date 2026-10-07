# src/main.py
import logging
import traceback
import asyncio
import uuid
from contextvars import ContextVar
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
import sentry_sdk

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# --- Security & Tracing ---
from src.security.rate_limiter import limiter
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")

# Database & Configuration
from src.config import settings
from src.database.session import engine, get_db
from src.middleware.request_limits import RequestBodyLimitMiddleware
from src.services.task_registry import retain_task

# --- Services ---
from src.services.communication.email import email_service 

# --- Router Imports ---
from src.routers import auth, leads, phones, sessions, facebook, settings as settings_router
from src.routers import partners, system, provisioning, storage
from src.routers import health
from src.routers.billing import checkout, invoices
from src.routers.webhooks import twilio, meshulam, whatsapp, marketing, campaign

# --- Logging Setup (Global JSON Structured Logging) ---
from pythonjsonlogger.json import JsonFormatter

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_ctx_var.get()
        return True

def setup_json_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    log_handler = logging.StreamHandler()
    formatter = JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(request_id)s %(name)s %(message)s',
        rename_fields={"levelname": "level", "asctime": "timestamp"}
    )
    log_handler.setFormatter(formatter)
    log_handler.addFilter(RequestIdFilter())
    root_logger.addHandler(log_handler)

    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = [log_handler]
        uvicorn_logger.propagate = False

setup_json_logging()
logger = logging.getLogger("LeadFlowSystem")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting System...")
    logger.info("🗄️ Database schema is managed by Alembic migrations.")
    yield
    logger.info("🛑 Shutting down gracefully... Cleaning up resources.")
    engine.dispose()

if getattr(settings, "SENTRY_DSN", None):
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

app = FastAPI(title=settings.APP_NAME, version="3.0.0", lifespan=lifespan)

# ==============================================================================
# 🛡️ SECURITY & TRACING MIDDLEWARE
# ==============================================================================

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Injects a unique Request ID into every request for distributed tracing."""
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_ctx_var.set(req_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # HARDENED CSP: API should only return JSON, never execute inline scripts or frames.
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
    return response

@app.middleware("http")
async def dlp_trigger_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if (path.startswith("/api/v1") and not path.startswith("/api/v1/auth")) or path.startswith("/webhooks") or path == "/test-leak":
        response.headers["X-Data-TTL"] = "1"
    return response
    
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ==============================================================================
# 🚨 GLOBAL EXCEPTION HANDLER
# ==============================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if getattr(settings, "SENTRY_DSN", None):
        sentry_sdk.capture_exception(exc)
        
    error_summary = str(exc)
    stack_trace = traceback.format_exc()
    logger.error(f"Internal Server Error: {error_summary}")

    client_ip = request.client.host if request.client else "Unknown"
    request_info = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": client_ip,
        "request_id": request_id_ctx_var.get()
    }

    retain_task(
        asyncio.create_task(
            email_service.send_error_alert_email(
                error_summary=error_summary,
                stack_trace=stack_trace,
                request_info=request_info,
            )
        )
    )

    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "אופס! משהו השתבש בצד שלנו. הצוות הטכני קיבל דיווח ויטפל בזה בהקדם.", "request_id": request_info["request_id"]}
    )

# --- General Middleware Stack ---
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["my-leads.app", "*.my-leads.app", "localhost", "127.0.0.1"])
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://my-leads.app", "https://www.my-leads.app", "http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(RequestBodyLimitMiddleware)

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

app.include_router(provisioning.router)
app.include_router(twilio.router, prefix="/webhooks/twilio", tags=["Webhooks - Twilio"])
app.include_router(whatsapp.router, prefix="/webhooks/whatsapp", tags=["Webhooks - WhatsApp"])
app.include_router(meshulam.router, prefix="/webhooks/meshulam", tags=["Webhooks - Meshulam"])
app.include_router(marketing.router)
app.include_router(campaign.router)
app.include_router(system.router)
app.include_router(storage.router)
app.include_router(health.router)

# ==============================================================================
# 🏥 HEALTH PROBES
# ==============================================================================
@app.get("/health/live", tags=["System"])
@limiter.limit("5/minute")
async def liveness_probe(request: Request):
    """Basic check to ensure the API process is running."""
    return {"status": "online", "version": "3.0.0", "mode": settings.APP_ENV}

@app.get("/health/ready", tags=["System"])
@limiter.limit("5/minute")
def readiness_probe(request: Request, db: Session = Depends(get_db)):
    """Deep check to ensure the API can connect to the Database and Redis."""
    try:
        # Verify DB connection
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "database_error"})