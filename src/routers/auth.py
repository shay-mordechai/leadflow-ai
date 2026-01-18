# src/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt # New import for JWT
import secrets
import string

from src.database.session import get_db
from src.database.models import User, PlanTier

router = APIRouter()

# --- Security Configuration ---
# In production, move these to your .env file
SECRET_KEY = "your-super-secret-key-change-me" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440 # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Schemas ---
class RegisterSchema(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    password: Optional[str] = None 
    personal_whatsapp: str
    business_whatsapp: Optional[str] = None
    needs_new_number: bool = False
    business_type: str
    other_business_type: Optional[str] = None
    plan: str = "start"

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

# --- Helper Functions ---
def create_access_token(data: dict):
    """Generates a real JWT token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Routes ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(data: RegisterSchema, db: Session = Depends(get_db)):
    """Registers user with an automated secure password."""
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Generate automated password
    alphabet = string.ascii_letters + string.digits
    generated_pass = ''.join(secrets.choice(alphabet) for _ in range(12))
    
    hashed = pwd_context.hash(generated_pass)
    tier_mapping = {"start": PlanTier.STARTER, "pro": PlanTier.PRO}
    selected_tier = tier_mapping.get(data.plan.lower(), PlanTier.STARTER)

    new_user = User(
        name=data.name,
        email=data.email,
        hashed_password=hashed,
        is_active=True,
        personal_whatsapp=data.personal_whatsapp,
        business_type=data.business_type,
        plan_tier=selected_tier
    )

    try:
        db.add(new_user)
        db.commit()
        return {
            "status": "success",
            "temporary_password": generated_pass,
            "email": data.email
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/login")
async def login_user(data: LoginSchema, db: Session = Depends(get_db)):
    """Authenticates user and returns a real JWT."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not pwd_context.verify(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate real token using the user's email as the subject (sub)
    access_token = create_access_token(data={"sub": user.email})
    
    return {"access_token": access_token, "token_type": "bearer"}
