# src/routers/ui.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Security Import
from src.security.dependencies import get_current_user
from src.database.models import User

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")

# Configuration for contact details
SUPPORT_EMAIL = "support@my-leads.app"

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Public Home Page / Marketing Landing Page.
    """
    return templates.TemplateResponse("marketing.html", {"request": request})

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """
    Public Registration Page.
    """
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Public Login Page.
    """
    return templates.TemplateResponse("login.html", {"request": request})

# --- Trust & Legal Pages (Required for Meta Verification & User Trust) ---

@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """
    Privacy Policy Page.
    Critical for Meta App Review and user trust.
    """
    return templates.TemplateResponse("privacy.html", {
        "request": request, 
        "email": SUPPORT_EMAIL
    })

@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    """
    Terms of Service Page.
    Legal disclaimer regarding AI accuracy and liability.
    """
    return templates.TemplateResponse("terms.html", {
        "request": request,
        "email": SUPPORT_EMAIL
    })

@router.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    """
    Contact Us Page.
    """
    return templates.TemplateResponse("contact.html", {
        "request": request, 
        "email": SUPPORT_EMAIL
    })

# --- Protected Application Routes ---

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_user) # <--- SECURITY CHECK
):
    """
    PROTECTED PAGE: Only accessible with a valid token/cookie.
    The 'current_user' object contains all the user's details from the DB.
    """
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "plan_name": current_user.plan_tier.value
    })