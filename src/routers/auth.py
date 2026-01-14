from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from src.database.session import get_db
from src.database.models import User

router = APIRouter()

# --- Schemas ---
# Defines what data we expect from the frontend during registration
class RegisterSchema(BaseModel):
    name: str
    email: EmailStr
    password: str
    # Optional: We can add 'business_name' or 'phone' later if needed

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

# --- Routes ---

@router.post("/register")
async def register_user(data: RegisterSchema, db: Session = Depends(get_db)):
    """
    Registers a new SaaS user.
    """
    # 1. Check if email already exists
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )

    # 2. Create new User instance
    # TODO: In production, use bcrypt to hash the password!
    # e.g., hashed_pw = pwd_context.hash(data.password)
    new_user = User(
        name=data.name,
        email=data.email,
        hashed_password=data.password, # Storing plain text for DEV only
        plan_tier="STARTER",           # Default plan
        is_active=True
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "status": "success",
            "user_id": str(new_user.id),
            "message": "Account created successfully"
        }
    except Exception as e:
        db.rollback()
        print(f"Database Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration"
        )

@router.post("/login")
async def login_user(data: LoginSchema, db: Session = Depends(get_db)):
    """
    Simple login that returns a mock token.
    """
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Simple password check
    if user.hashed_password != data.password:
        raise HTTPException(status_code=403, detail="Invalid credentials")
    
    # Return a fake token (dependencies.py will accept this)
    return {
        "access_token": "fake-jwt-token-dev-mode",
        "token_type": "bearer",
        "user_name": user.name
    }