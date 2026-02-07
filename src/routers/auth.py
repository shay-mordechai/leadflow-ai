# src/routers/auth.py
import logging
import random
import string
from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import User, PhoneNumber, PlanTier
from src.config import settings
from src.services.email import send_otp_email 
from src.schemas.user import UserCreate, UserResponse, VerifyOTP
from src.security.dependencies import get_current_user
# Security Fix: Use centralized hashing
from src.security.hashing import get_hash, verify_hash

router = APIRouter()
logger = logging.getLogger("AuthSecurity")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@router.get("/me", response_model=UserResponse)
async def read_users_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    phone = db.query(PhoneNumber).filter(PhoneNumber.owner_id == user.id).first()
    user_data = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    user_data['assigned_phone'] = phone.number if phone else None
    return user_data

@router.post("/register", status_code=201)
async def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email registered")
    
    tier = PlanTier.PRO if "PRO" in (data.plan_tier or "").upper() else PlanTier.STARTER
    
    # Use centralized get_hash (SHA256 + Bcrypt)
    secure_hash = get_hash(data.password)
    
    new_user = User(
        email=data.email, 
        hashed_password=secure_hash,
        name=data.full_name, 
        business_name=data.business_name,
        business_type=data.business_type, 
        plan_tier=tier, 
        is_active=True
    )
    db.add(new_user)
    db.commit()
    return {"status": "success"}

@router.post("/login")
async def login(bg_tasks: BackgroundTasks, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    
    # Use centralized verify_hash
    if not user or not verify_hash(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    otp = ''.join(random.choices(string.digits, k=6))
    user.otp_code = otp
    db.commit()
    
    logger.info(f"📧 OTP for {user.email}: {otp}")
    bg_tasks.add_task(send_otp_email, user.email, otp)
    return {"message": "OTP sent", "mfa_required": True}

@router.post("/verify-otp")
async def verify_otp(data: VerifyOTP, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or user.otp_code != data.otp_code:
        raise HTTPException(status_code=401, detail="Invalid OTP")
    
    user.otp_code = None
    db.commit()
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {"access_token": token, "token_type": "bearer"}