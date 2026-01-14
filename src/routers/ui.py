from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Security Import
from src.security.dependencies import get_current_user
from src.database.models import User

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Public Home Page
    return templates.TemplateResponse("marketing.html", {"request": request})

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    # Public Registration
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Public Login
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_user) # <--- SECURITY CHECK
):
    """
    PROTECTED PAGE: Only accessible with a valid token.
    The 'current_user' object contains all the user's details from the DB.
    """
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user, # Passing user data to the HTML template
        "plan_name": current_user.plan_tier.value
    })