from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Independent UI router
router = APIRouter()
templates = Jinja2Templates(directory="src/templates")

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Professional comment: Render the home page
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    # Professional comment: Render the registration page
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Professional comment: Render the login page
    return templates.TemplateResponse("login.html", {"request": request})
