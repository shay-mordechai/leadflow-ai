# src/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.database.session import engine, Base
from src.routers import auth, phones, payments, webhooks, settings as settings_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LeadFlowSystem")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting System...")
    Base.metadata.create_all(bind=engine)
    yield
    logger.info("🛑 Shutting down...")

app = FastAPI(title="LeadFlow AI", version="2.7.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(phones.router, prefix="/api/v1/phones", tags=["Phones"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])

@app.get("/health")
def health_check():
    return {"status": "online", "mode": "Prod"}