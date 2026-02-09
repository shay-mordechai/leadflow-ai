# src/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Database & Config
from src.config import settings
from src.database.session import engine, Base

# --- Router Imports ---
# 1. Core Routers
from src.routers import auth, leads, phones, sessions, settings as settings_router

# 2. Billing Routers (Split from payments.py)
from src.routers.billing import checkout, invoices

# 3. Webhooks Routers (Split from webhooks.py)
from src.routers.webhooks import twilio, meshulam, whatsapp

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LeadFlowSystem")

# --- Lifecycle Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting System...")
    # Create Tables (Quick & Dirty for Dev/QA. Use Alembic for Prod later)
    Base.metadata.create_all(bind=engine)
    yield
    logger.info("🛑 Shutting down...")

# --- App Definition ---
app = FastAPI(title="LeadFlow AI", version="3.0.0", lifespan=lifespan)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In strict prod, change this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 🔗 ROUTER REGISTRATION
# ==============================================================================

# --- 1. Main API (V1) ---
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["Leads"])
app.include_router(phones.router, prefix="/api/v1/phones", tags=["Phones"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])

# --- 2. Billing API ---
# Both mount to /api/v1/billing, serving different endpoints
app.include_router(checkout.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(invoices.router, prefix="/api/v1/billing", tags=["Billing"])

# --- 3. Webhooks (External Callbacks) ---
# Separated by provider for clean routing
app.include_router(twilio.router, prefix="/webhooks/twilio", tags=["Webhooks - Twilio"])
app.include_router(whatsapp.router, prefix="/webhooks/whatsapp", tags=["Webhooks - WhatsApp"])
app.include_router(meshulam.router, prefix="/webhooks/meshulam", tags=["Webhooks - Meshulam"])

# ==============================================================================
# 🏥 HEALTH CHECK
# ==============================================================================
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "online", 
        "version": "3.0.0",
        "mode": settings.APP_ENV
    }