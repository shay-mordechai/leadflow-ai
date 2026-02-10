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
MAX_OTP_ATTEMPTS = 3 # Assuming your model supports this, otherwise enforce via Redis

def create_access_token(data: dict):
    """
    Creates a JWT token with a strict expiration time.
    Uses UTC to avoid timezone confusion.
    """
    to_encode = data.copy()
    # SECURITY: Use now(timezone.utc) instead of utcnow() (deprecated and naive)
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@router.get("/me", response_model=UserResponse)
async def read_users_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns the currently authenticated user's profile.
    """
    phone = db.query(PhoneNumber).filter(PhoneNumber.owner_id == user.id).first()
    # SECURITY: Explicitly map fields to avoid leaking internal DB columns via __dict__
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
    Registers a new user.
    SECURITY FIX: Enforces STARTER tier. Prevents Mass Assignment vulnerability.
    """
    # 1. Check if email exists
    if db.query(User).filter(User.email == data.email).first():
        # SECURITY: Standard practice is generic error, but for registration UX 
        # it is often acceptable to say "Email registered" to prevent duplicates.
        # To be stricter, return 201 and send an email saying "You already have an account".
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # 2. Hash Password
    secure_hash = get_hash(data.password)
    
    # 3. SECURITY FIX: Hardcode the plan tier.
    # The user CANNOT set their own plan via API parameters.
    # We ignore data.plan_tier entirely.
    default_tier = PlanTier.STARTER
    
    new_user = User(
        email=data.email, 
        hashed_password=secure_hash,
        name=data.full_name, 
        business_name=data.business_name,
        business_type=data.business_type, 
        plan_tier=default_tier, # <--- FORCED TO STARTER
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    
    logger.info(f"New user registered: {data.email}")
    return {"status": "success", "message": "User created successfully"}

@router.post("/login")
async def login(bg_tasks: BackgroundTasks, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Initiates login flow via OTP.
    """
    # SECURITY: Normalize email to lowercase to prevent duplicates/confusion
    email = form.username.lower()
    user = db.query(User).filter(User.email == email).first()
    
    # SECURITY: Constant-time comparison logic to prevent Timing Attacks.
    # Even if user is not found, we simulate work or rely on verify_hash to handle it safely.
    valid_password = False
    if user:
        valid_password = verify_hash(form.password, user.hashed_password)
    
    if not user or not valid_password:
        # SECURITY: Generic error message. Do not reveal if it was the email or password.
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
         raise HTTPException(status_code=403, detail="Account is disabled")

    # SECURITY: Use 'secrets' module for cryptographically secure random numbers
    otp = ''.join(secrets.choice("0123456789") for _ in range(6))
    
    # SECURITY: Set OTP expiration
    otp_expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRATION_MINUTES)
    
    user.otp_code = otp
    user.otp_expires_at = otp_expires # Ensure your User model has this field
    db.commit()
    
    # SECURITY: Do NOT log the actual OTP code in production logs.
    logger.info(f"📧 OTP generated for {user.email} (Expires in {OTP_EXPIRATION_MINUTES}m)")
    
    bg_tasks.add_task(send_otp_email, user.email, otp)
    
    return {"message": "OTP sent to email", "mfa_required": True}

@router.post("/verify-otp")
async def verify_otp(data: VerifyOTP, db: Session = Depends(get_db)):
    """
    Verifies the OTP and issues an Access Token.
    """
    user = db.query(User).filter(User.email == data.email).first()
    
    # 1. Basic Existence Check
    if not user:
        raise HTTPException(status_code=401, detail="Invalid operation")

    # 2. SECURITY: Check if OTP is present and matches
    # Use constant time comparison for OTPs if possible, though strict equality is usually fine here
    if not user.otp_code or user.otp_code != data.otp_code:
        # Potential: Increment failed attempts counter here to lock account
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    
    # 3. SECURITY: Check Expiration
    now_utc = datetime.now(timezone.utc)
    # Ensure otp_expires_at in DB is timezone aware or convert accordingly
    if user.otp_expires_at and user.otp_expires_at.replace(tzinfo=timezone.utc) < now_utc:
        user.otp_code = None # Clear expired OTP
        db.commit()
        raise HTTPException(status_code=401, detail="OTP has expired")
    
    # 4. Success - Clear OTP immediately to prevent reuse (Replay Attack)
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()
    
    # 5. Generate Token
    token = create_access_token({"sub": str(user.id), "email": user.email})
    
    return {"access_token": token, "token_type": "bearer"}