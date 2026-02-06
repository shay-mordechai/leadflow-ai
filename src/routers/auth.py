# src/routers/auth.py
import random
import string
import logging
from datetime import timedelta, datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from passlib.context import CryptContext

# Internal Imports
from src.database.session import get_db
from src.database.models import User, PhoneNumber # Added PhoneNumber
from src.config import settings
from src.services.email import send_otp_email 
from src.schemas.user import UserCreate, UserResponse, VerifyOTP

router = APIRouter()
logger = logging.getLogger("AuthSecurity")

# --- Security Configuration ---
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

# --- Dependency: Authentication ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
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
    
    return user

# --- Routes ---

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the current user profile.
    
    CRITICAL UPDATE:
    We manually query the PhoneNumber table to populate the 'assigned_phone' field.
    This tells the Frontend if the user needs to be redirected to the Onboarding/Buy-Number page.
    """
    # 1. Fetch assigned phone number
    phone_record = db.query(PhoneNumber).filter(PhoneNumber.owner_id == current_user.id).first()
    
    # 2. Convert SQLAlchemy object to dictionary to allow modification
    user_data = current_user.__dict__
    
    # 3. Inject the phone number (or None)
    if phone_record:
        user_data['assigned_phone'] = phone_record.number
    else:
        user_data['assigned_phone'] = None
        
    return user_data

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = get_password_hash(data.password)
    
    user_data = {
        "email": data.email,
        "hashed_password": hashed_pw,
        "is_active": True,
        "name": data.full_name,
        "business_name": data.business_name,
        "business_type": data.business_type,
        "plan_type": data.plan_tier if data.plan_tier else "free"
    }

    try:
        new_user = User(**user_data)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"status": "success", "message": "User registered successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Registration Error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@router.post("/login")
async def login_step_1(
    background_tasks: BackgroundTasks, 
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    otp = generate_otp()
    
    if hasattr(user, "otp_code"):
        try:
            user.otp_code = otp
            user.otp_expires_at = datetime.utcnow() + timedelta(minutes=5)
            db.commit()
        except Exception as e:
             logger.error(f"Failed to save OTP: {e}")
    
    logger.info(f"📧 Queueing OTP email for {user.email}")
    background_tasks.add_task(send_otp_email, user.email, otp)

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
    
    plan = "free"
    if hasattr(user, "plan_type"): 
        plan = str(user.plan_type)
    
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "plan": plan}
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "user_name": getattr(user, "name", "User")
    }