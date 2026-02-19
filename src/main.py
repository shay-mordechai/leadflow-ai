# src/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Database & Config
from src.config import settings
from src.database.session import engine, Base

# --- Router Imports ---
from src.routers import auth, leads, phones, sessions, facebook, settings as settings_router
from src.routers.billing import checkout, invoices
from src.routers.webhooks import twilio, meshulam, whatsapp

# --- Security: Cloudflare Aware Rate Limiter ---
def get_real_ip(request: Request):
    """
    Security: Retrieves the actual client IP behind Cloudflare.
    If 'CF-Connecting-IP' is missing, falls back to direct connection IP.
    """
    return request.headers.get("CF-Connecting-IP", get_remote_address(request))

limiter = Limiter(key_func=get_real_ip)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LeadFlowSystem")

# --- Lifecycle Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting System...")
    # Security Note: In Production, use Alembic for migrations, not create_all
    Base.metadata.create_all(bind=engine)
    yield
    logger.info("🛑 Shutting down...")

# --- App Definition ---
app = FastAPI(title="LeadFlow AI", version="3.0.0", lifespan=lifespan)

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
    Security: Catches internal errors (SQLAlchemy, Python code) 
    and returns a generic 500 error to the client.
    Prevents Information Disclosure (Stack Traces).
    """
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
app.include_router(twilio.router, prefix="/webhooks/twilio", tags=["Webhooks - Twilio"])
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