import time
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session

# Professional English Comment: Internal project imports
from src.config import settings
from src.database.session import engine, get_db
from src.database.models import Base
from src.logging_config import setup_logging
from src.middleware.rate_limit import RateLimitMiddleware
from src.routers import leads, sessions

# Initialize professional logging
logger = setup_logging()

app = FastAPI(
    title="My-Leads AI",
    description="Minimalist & Secure Lead Management API",
    version="2.5.0"
)

# --- Security & Middlewares ---

# 1. Custom Rate Limiting (Protects against DoS without external tools)
app.add_middleware(RateLimitMiddleware, max_requests=60, window_seconds=60)

# 2. Trusted Host Middleware (Prevents Host Header Injection)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# 3. CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_and_timing_headers(request: Request, call_next):
    """
    Adds security headers to every response and logs processing time.
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"

    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response

# --- Static Files & Templates ---
app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

# --- Routers ---
app.include_router(leads.router, prefix="/api/v1/leads")
app.include_router(sessions.router, prefix="/api/v1/sessions")

# --- System Routes ---

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Production health check for Docker/Kubernetes.
    Checks Database connectivity.
    """
    try:
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected", "version": "2.5.0"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

@app.on_event("startup")
def startup_event():
    """
    Actions to perform on application start.
    """
    logger.info("Initializing My-Leads AI Application...")
    try:
        # Create database tables if they don't exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema verified/created successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("marketing.html", {"request": request})
