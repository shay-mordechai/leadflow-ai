# src/main.py
import time
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

# Internal Project Imports
from src.config import settings
from src.database.session import engine, get_db
from src.database.models import Base

# Import Routers
from src.routers import leads, auth, webhooks, settings as settings_router
from src.routers import ui 
from src.routers import payments

# Professional English Comment:
# Configure Root Logger for centralized logging.
# In Production, these logs are captured by Podman/Docker logs.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LeadFlowSystem")

# --- Lifespan Context Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    Ensures the database is reachable and the schema is initialized.
    """
    logger.info(f"🚀 Starting up {settings.APP_NAME} System...")
    
    try:
        # Professional English Comment:
        # metadata.create_all is used here for MVP/Fast deployment.
        # It checks for table existence before creation to avoid operational errors.
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database schema verified/initialized successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Database init skipped (likely initialized by another worker): {e}")
        # We don't exit here to allow for manual inspection via /health endpoint
    
    yield 
    
    logger.info(f"🛑 Shutting down {settings.APP_NAME} System...")

# Initialize FastAPI Application
app = FastAPI(
    title=settings.APP_NAME,
    version="2.7.0",
    lifespan=lifespan,
    # Disable Swagger UI in production unless DEBUG is explicitly enabled
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None
)

# --- Middleware Configuration ---

# Ensure the application only responds to allowed domains (Cloudflare/EC2 IP)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# Cross-Origin Resource Sharing (CORS) Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific domain for better security
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """
    Custom middleware to inject security headers and measure processing time.
    """
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Performance & Security Headers
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Professional English Comment:
        # HSTS ensures the browser only communicates over HTTPS.
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
        return response
    except Exception as e:
        logger.error(f"🔥 Unhandled Middleware Exception: {e}")
        return JSONResponse(
            status_code=500, 
            content={"detail": "Internal Server Error", "error_type": "MiddlewareCrash"}
        )

# --- Static Files Service ---
# Ensure the static directory exists before mounting to avoid startup crashes
os.makedirs("src/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# --- Router Registration ---

# 1. API v1 Core Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["Leads Management"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["AI Configuration"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks Integration"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Billing & Subscriptions"])

# 2. Frontend / UI Routes
app.include_router(ui.router, tags=["User Interface"])

# --- System & Diagnostic Routes ---

@app.get("/health", tags=["System Maintenance"])
def health_check(db: Session = Depends(get_db)):
    """
    Liveness and Readiness probe to monitor system health.
    """
    try:
        # Verify database connectivity
        db.execute(text("SELECT 1"))
        return {
            "status": "online", 
            "database": "connected", 
            "version": app.version,
            "mode": "Development" if settings.DEBUG else "Production"
        }
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database Connectivity Lost")