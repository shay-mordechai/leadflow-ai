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
from src.database.models import User
from src.config import settings
from src.services.email import send_otp_email 
# Import the schemas defined in user.py for strict validation and response filtering
from src.schemas.user import UserCreate, UserResponse, VerifyOTP

router = APIRouter()
logger = logging.getLogger("AuthSecurity")

# --- Security Configuration ---
# CryptContext handles password hashing using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# OAuth2PasswordBearer extracts the token from the Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def verify_password(plain_password, hashed_password):
    """Verifies a plain text password against a hashed version."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Generates a bcrypt hash for a plain text password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Generates a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def generate_otp(length=6) -> str:
    """Generates a random numeric OTP code."""
    return ''.join(random.choices(string.digits, k=length))

# --- Dependency: Authentication & User Retrieval ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Validates the JWT token and returns the raw SQLAlchemy User object.
    
    SECURITY NOTE: 
    This function returns the FULL user object including sensitive fields (password_hash, etc.).
    It is intended for INTERNAL server logic only.
    Any endpoint returning this data to the client MUST use response_model=UserResponse.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode the JWT token using the application's secret key
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("email") or payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Check if the user exists in the database
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    
    return user

# --- Routes ---

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    RSC COMPATIBLE ENDPOINT:
    Returns the current user profile.
    FastAPI uses the response_model=UserResponse to filter the 'current_user' ORM object,
    automatically stripping out sensitive fields like password_hash before sending JSON.
    """
    return current_user

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(data: UserCreate, db: Session = Depends(get_db)):
    """Handles new user registration and stores hashed passwords."""
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = get_password_hash(data.password)
    
    # Construct database model from incoming schema data
    user_data = {
        "email": data.email,
        "hashed_password": hashed_pw,
        "is_active": True,
        "name": data.full_name, # Map full_name to name in DB
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
    """Step 1 of Authentication: Verifies credentials and sends an OTP."""
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    otp = generate_otp()
    
    # Store OTP code and expiration in the database
    if hasattr(user, "otp_code"):
        try:
            user.otp_code = otp
            user.otp_expires_at = datetime.utcnow() + timedelta(minutes=5)
            db.commit()
        except Exception as e:
             logger.error(f"Failed to save OTP: {e}")
    
    # Send MFA OTP via background task to avoid blocking the request
    logger.info(f"📧 Queueing OTP email for {user.email}")
    background_tasks.add_task(send_otp_email, user.email, otp)

    return {"message": "OTP sent to email", "mfa_required": True, "email": user.email}

@router.post("/verify-otp")
async def verify_otp_step_2(data: VerifyOTP, db: Session = Depends(get_db)):
    """Step 2 of Authentication: Verifies the OTP and issues a JWT token."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate OTP if the user model supports it
    if hasattr(user, "otp_code") and user.otp_code:
        if user.otp_code != data.otp_code:
             raise HTTPException(status_code=401, detail="Invalid OTP code")
        
        # Invalidate OTP after successful verification
        user.otp_code = None
        db.commit()
    
    # Retrieve user plan for token claims
    plan = "free"
    if hasattr(user, "plan_type"): 
        plan = str(user.plan_type)
    
    # Create the final access token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "plan": plan}
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "user_name": getattr(user, "name", "User")
    }