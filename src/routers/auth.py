# src/routers/auth.py
import random
import string
import logging
from datetime import timedelta, datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Header, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext

# Internal Imports
from src.database.session import get_db
from src.database.models import User
from src.config import settings
# Import the new email service
from src.services.email import send_otp_email 

router = APIRouter()
logger = logging.getLogger("AuthSecurity")

# --- Inline Security Utils ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def generate_otp(length=6) -> str:
    return ''.join(random.choices(string.digits, k=length))

# --- Models ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    plan_tier: Optional[str] = "starter"

class VerifyOTP(BaseModel):
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)

# --- Dependency ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("email") or payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    
    plan = "free"
    if hasattr(user, "plan_type"): plan = str(user.plan_type).lower()
    elif hasattr(user, "plan_tier"): plan = str(user.plan_tier).lower()

    return {
        "user_id": str(user.id),
        "email": user.email,
        "plan_type": plan,
        "name": getattr(user, "name", "User")
    }

# --- Routes ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = get_password_hash(data.password)
    
    user_data = {
        "email": data.email,
        "hashed_password": hashed_pw,
        "is_active": True
    }
    if data.full_name: user_data["name"] = data.full_name
    if hasattr(User, "business_name"): user_data["business_name"] = data.business_name
    if hasattr(User, "business_type"): user_data["business_type"] = data.business_type
    if hasattr(User, "plan_type"): user_data["plan_type"] = "free"

    try:
        new_user = User(**user_data)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"status": "success", "message": "User registered successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Registration Error: {e}")
        # Fallback for schema mismatch
        try:
            minimal_user = User(email=data.email, hashed_password=hashed_pw, name=data.full_name, is_active=True)
            db.add(minimal_user)
            db.commit()
            return {"status": "success", "message": "User registered (minimal)"}
        except:
            raise HTTPException(status_code=500, detail="Registration failed")

@router.post("/login")
async def login_step_1(
    background_tasks: BackgroundTasks, # <-- NEW: For sending email in background
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    otp = generate_otp()
    
    # Save to DB
    if hasattr(user, "otp_code"):
        try:
            user.otp_code = otp
            user.otp_expires_at = datetime.utcnow() + timedelta(minutes=5)
            db.commit()
        except:
            pass 
    
    # --- SEND EMAIL (Background) ---
    logger.info(f"📧 Queueing OTP email for {user.email}")
    background_tasks.add_task(send_otp_email, user.email, otp)
    # -------------------------------

    return {"message": "OTP sent to email", "mfa_required": True, "email": user.email}

@router.post("/verify-otp")
async def verify_otp_step_2(data: VerifyOTP, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if hasattr(user, "otp_code") and user.otp_code:
        if user.otp_code != data.otp_code:
             raise HTTPException(status_code=401, detail="Invalid OTP code")
        user.otp_code = None
        db.commit()
    
    # Generate Token
    plan = "free"
    if hasattr(user, "plan_type"): plan = str(user.plan_type)
    
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "plan": plan}
    )
    
    return {"access_token": access_token, "token_type": "bearer", "user_name": getattr(user, "name", "User")}