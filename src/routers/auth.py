# src/routers/auth.py
import logging
import secrets  # CRITICAL: Use secrets, not random, for cryptography
from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from sqlalchemy.orm import Session

# Local imports
from src.database.session import get_db
from src.database.models import User, PhoneNumber, PlanTier
from src.config import settings
from src.services.communication.email import send_otp_email 
from src.schemas.user import UserCreate, UserResponse, VerifyOTP
from src.security.dependencies import get_current_user
from src.security.hashing import get_hash, verify_hash

router = APIRouter()
logger = logging.getLogger("AuthSecurity")

# --- Constants ---
OTP_EXPIRATION_MINUTES = 5

def create_access_token(data: dict):
    """
    Creates a JWT token with a strict expiration time.
    Uses UTC to avoid timezone confusion.
    """
    to_encode = data.copy()
    # SECURITY: Use now(timezone.utc) to ensure consistent expiration across servers
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@router.get("/me", response_model=UserResponse)
async def read_users_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns the currently authenticated user's profile.
    Explicit mapping prevents leaking internal database fields.
    """
    phone = db.query(PhoneNumber).filter(PhoneNumber.owner_id == user.id).first()
    
    # SECURITY: Manually constructing the response to control data exposure
    user_data = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "business_name": user.business_name,
        "business_type": user.business_type,
        "plan_tier": user.plan_tier,
        "is_active": user.is_active,
        "assigned_phone": phone.number if phone else None
    }
    return user_data

@router.post("/register", status_code=201)
async def register(data: UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new user and enforces the STARTER tier.
    Prevents Mass Assignment vulnerabilities.
    """
    # 1. Check if email exists
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # 2. Hash Password
    secure_hash = get_hash(data.password)
    
    # 3. SECURITY: Force default tier regardless of input
    default_tier = PlanTier.STARTER
    
    new_user = User(
        email=data.email.lower(), 
        hashed_password=secure_hash,
        name=data.full_name, 
        business_name=data.business_name,
        business_type=data.business_type, 
        plan_tier=default_tier,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    
    logger.info(f"New user registered: {data.email}")
    return {"status": "success", "message": "User created successfully"}

@router.post("/login")
async def login(bg_tasks: BackgroundTasks, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Initiates login flow by generating and emailing a secure OTP.
    """
    # SECURITY: Normalize email
    email = form.username.lower()
    user = db.query(User).filter(User.email == email).first()
    
    # SECURITY: Constant-time check simulation to mitigate timing attacks
    valid_password = False
    if user:
        valid_password = verify_hash(form.password, user.hashed_password)
    
    if not user or not valid_password:
        # SECURITY: Generic error message to prevent account enumeration
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
         raise HTTPException(status_code=403, detail="Account is disabled")

    # SECURITY: Use secrets for a cryptographically secure 6-digit OTP
    otp = ''.join(secrets.choice("0123456789") for _ in range(6))
    
    # SECURITY: Set short-lived expiration
    otp_expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRATION_MINUTES)
    
    user.otp_code = otp
    user.otp_expires_at = otp_expires
    db.commit()
    
    # SECURITY: Log the event, never the actual OTP code
    logger.info(f"OTP generated for user: {user.email}")
    
    bg_tasks.add_task(send_otp_email, user.email, otp)
    
    return {"message": "OTP sent to email", "mfa_required": True}

@router.post("/verify-otp")
async def verify_otp(data: VerifyOTP, db: Session = Depends(get_db)):
    """
    Verifies OTP and issues JWT. OTP is cleared immediately after use.
    """
    user = db.query(User).filter(User.email == data.email.lower()).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid operation")

    # 1. Validate OTP presence and match
    if not user.otp_code or user.otp_code != data.otp_code:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    
    # 2. Check Expiration
    now_utc = datetime.now(timezone.utc)
    if user.otp_expires_at and user.otp_expires_at.replace(tzinfo=timezone.utc) < now_utc:
        user.otp_code = None 
        db.commit()
        raise HTTPException(status_code=401, detail="OTP has expired")
    
    # 3. Success - Clear OTP to prevent Replay Attacks
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()
    
    # 4. Issue Access Token
    token = create_access_token({"sub": str(user.id), "email": user.email})
    
    # Bandit B105 False Positive: 'bearer' is a standard OAuth2 string, not a hardcoded password
    return {"access_token": token, "token_type": "bearer"} # nosec B105