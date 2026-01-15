# src/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field # Added Field for validation
from typing import Optional

from src.database.session import get_db
from src.database.models import User

router = APIRouter()

# --- Schemas ---
# Defines what data we expect from the frontend during registration
class RegisterSchema(BaseModel):
    # 'min_length' helps avoid 422 errors caused by empty strings
    name: str = Field(..., min_length=2, description="User's full name")
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    
    # Optional fields for future use
    # business_name: Optional[str] = None
    # phone: Optional[str] = None

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

# --- Routes ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(data: RegisterSchema, db: Session = Depends(get_db)):
    """
    Registers a new SaaS user.
    """
    print(f"📝 [Register Attempt] Email: {data.email}, Name: {data.name}") # Log for debugging

    # 1. Check if email already exists
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        print(f"❌ [Register Fail] Email already exists: {data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )

    # 2. Create new User instance
    # WARNING: Storing passwords in plain text is for DEVELOPMENT ONLY.
    # In production, you must use bcrypt (passlib) to hash this.
    new_user = User(
        name=data.name,
        email=data.email,
        hashed_password=data.password, # TODO: Replace with hashed_pw in Prod
        plan_tier="STARTER",           # Default plan
        is_active=True
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"✅ [Register Success] User created with ID: {new_user.id}")

        return {
            "status": "success",
            "user_id": str(new_user.id),
            "message": "Account created successfully"
        }
    except Exception as e:
        db.rollback()
        print(f"🔥 [Database Error] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/login")
async def login_user(data: LoginSchema, db: Session = Depends(get_db)):
    """
    Simple login that returns a mock token.
    """
    print(f"🔑 [Login Attempt] Email: {data.email}")

    user = db.query(User).filter(User.email == data.email).first()
    
    if not user:
        print("❌ [Login Fail] User not found")
        raise HTTPException(status_code=404, detail="User not found")
    
    # Simple password check (Compare plain text for now)
    if user.hashed_password != data.password:
        print("❌ [Login Fail] Invalid password")
        raise HTTPException(status_code=403, detail="Invalid credentials")
    
    print(f"✅ [Login Success] User: {user.name}")
    
    # Return a fake token (dependencies.py will accept this for dev mode)
    return {
        "access_token": "fake-jwt-token-dev-mode",
        "token_type": "bearer",
        "user_name": user.name
    }