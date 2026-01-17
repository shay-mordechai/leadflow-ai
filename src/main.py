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
# Note: Ensure you have a 'ui.py' router or keep the logic in main if it's small. 
# For this structure, I assume 'ui' exists or is handled via separate templates logic.
# If 'ui.py' handles the HTML serving, keep it. 
# If not, the template rendering logic should be here or in a dedicated views router.
from src.routers import ui 

# Configure Root Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LeadFlowSystem")

# --- Lifespan Context Manager (Modern Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database
    logger.info("🚀 Starting up AI LeadFlow System...")
    try:
        # Create tables (For Dev/MVP - In production use Alembic migrations)
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database schema initialized successfully.")
    except Exception as e:
        logger.critical(f"❌ Database initialization failed: {e}")
        # In a real app, we might want to stop here, but for now we continue
    
    yield # Application runs here
    
    # Shutdown: Clean up resources if needed
    logger.info("🛑 Shutting down AI LeadFlow System...")

# Initialize FastAPI Application
app = FastAPI(
    title=settings.APP_NAME,
    version="2.6.0", # Bumped version
    lifespan=lifespan, # Using the new lifespan manager
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None
)

# --- Middleware Configuration ---
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# CORS: Allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev purposes. In prod, use settings.ALLOWED_HOSTS
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """
    Adds security headers and logs processing time.
    """
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add Metrics & Security Headers
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # HSTS (Strict Transport Security) only for Production
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
        return response
    except Exception as e:
        logger.error(f"🔥 Unhandled Middleware Exception: {e}")
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

# --- Static Files ---
# Mounts the 'static' directory to serve CSS/JS/Images
os.makedirs("src/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# --- Router Registration ---

# 1. API Routes (Data & Logic)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["Leads Management"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["AI Configuration"]) # The Brain!
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])

# 2. UI Routes (HTML Pages)
# Assumes src/routers/ui.py handles returning HTMLTemplates
app.include_router(ui.router, tags=["User Interface"])

# --- System Routes ---

@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """
    Checks system vitality and database connectivity.
    """
    try:
        # Simple query to check DB connection
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy", 
            "database": "online", 
            "version": app.version,
            "environment": "Development" if settings.DEBUG else "Production"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database Unavailable")