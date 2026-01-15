# src/main.py
import time
import logging
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
# Import the new UI router and the Leads API router
from src.routers import leads, ui, auth, webhooks

# Configure Root Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LeadFlowSystem")

# Initialize FastAPI Application
app = FastAPI(
    title=settings.APP_NAME,
    version="2.5.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None
)

# --- Middleware Configuration ---
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
    except Exception as e:
        logger.error(f"Unhandled Middleware Exception: {e}")
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

# --- Static Files ---
import os
os.makedirs("src/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# --- Router Registration ---

# 1. API Routes (JSON Data)
app.include_router(leads.router, prefix="/api/v1/leads")
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(webhooks.router, prefix="/webhooks")

# 2. UI Routes (HTML Pages)
app.include_router(ui.router)

# --- System Routes ---
@app.on_event("startup")
def startup_event():
    logger.info("Starting up AI LeadFlow System...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")

@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "online", "version": app.version}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database Unavailable")
