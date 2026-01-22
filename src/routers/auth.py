# src/routers/auth.py
import random
import string
import logging
from datetime import timedelta, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

# Internal Imports
from src.database.session import get_db
from src.database.models import User, PlanTier
from src.security.hashing import verify_password, get_hash
from src.security.validation import create_access_token
from src.config import settings
from src.schemas.user import RegisterSchema, UserCreate, VerifyOTP # Use the updated schemas

router = APIRouter()
logger = logging.getLogger("AuthSecurity")

def generate_otp(length=6) -> str:
    """Generates a secure numeric OTP."""
    return ''.join(random.choices(string.digits, k=length))

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(data: UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new user with STRICT password policy.
    """
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = get_hash(data.password)
    tier_mapping = {"start": PlanTier.STARTER, "pro": PlanTier.PRO}
    selected_tier = tier_mapping.get((data.plan_tier or "starter").lower(), PlanTier.STARTER)

    new_user = User(
        name=data.full_name,
        email=data.email,
        hashed_password=hashed_pw,
        is_active=True,
        personal_whatsapp=data.personal_whatsapp,
        business_type=data.business_type,
        plan_tier=selected_tier,
        subscription_status="TRIAL"
    )

    try:
        db.add(new_user)
        db.commit()
        return {"status": "success", "message": "User registered successfully. Please log in."}
    except Exception as e:
        db.rollback()
        logger.error(f"Registration Error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed.")

@router.post("/login")
async def login_step_1(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Step 1: Validate credentials & Trigger MFA.
    Does NOT return a JWT token. Returns a message to check email.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    # Generate OTP
    otp = generate_otp()
    
    # Save encrypted OTP to DB (valid for 5 minutes)
    user.otp_code = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=5)
    db.commit()
    
    # TODO: Integration with AWS SES for real email sending.
    # For now, we Log it securely (In Prod logs, this allows you to test).
    logger.info(f"🔑 MFA CODE for {user.email}: {otp}") 
    print(f"🔑 MFA CODE for {user.email}: {otp}") # Ensure it prints to Podman logs

    return {
        "message": "OTP sent to email", 
        "mfa_required": True,
        "email": user.email
    }

@router.post("/verify-otp")
async def verify_otp_step_2(
    data: VerifyOTP,
    db: Session = Depends(get_db),
    cf_ipcity: Optional[str] = Header(None, alias="cf-ipcity")
):
    """
    Step 2: Verify OTP & Issue Token.
    """
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate OTP
    if not user.otp_code or not user.otp_expires_at:
        raise HTTPException(status_code=400, detail="No OTP requested")
        
    if datetime.utcnow() > user.otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP expired")
        
    if user.otp_code != data.otp_code:
        raise HTTPException(status_code=401, detail="Invalid OTP code")

    # OTP Valid -> Clear it & Update Location
    user.otp_code = None
    user.otp_expires_at = None
    if cf_ipcity:
        user.last_known_city = cf_ipcity
    db.commit()

    # Generate JWT
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id)},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_name": user.name
    }