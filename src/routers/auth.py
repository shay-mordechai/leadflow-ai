# src/routers/auth.py
# src/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from passlib.context import CryptContext

from src.database.session import get_db
from src.database.models import User, PlanTier

router = APIRouter()

# --- Schemas ---
class RegisterSchema(BaseModel):
    name: str = Field(..., min_length=2, description="User's full name")
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    
    personal_whatsapp: str = Field(..., description="Personal phone for notifications")
    
    business_whatsapp: Optional[str] = None
    needs_new_number: bool = False
    
    business_type: str
    other_business_type: Optional[str] = None
    
    # Frontend sends "start" or "pro", Backend maps to PlanTier Enum
    plan: str = "start"

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

# --- Routes ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(data: RegisterSchema, db: Session = Depends(get_db)):
    """
    Registers a new SaaS user with extended profile data.
    """
    print(f"📝 [Register Attempt] Email: {data.email}, Plan: {data.plan}")

    # 1. Check if email already exists
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        print(f"❌ [Register Fail] Email already exists: {data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )

    # 2. Resolve Business Type
    final_business_type = data.business_type
    if data.business_type == "Other" and data.other_business_type:
        final_business_type = data.other_business_type

    # 3. Resolve Plan Tier (Map string to Enum)
    # Default to STARTER if input is unknown
    tier_mapping = {
        "start": PlanTier.STARTER,
        "pro": PlanTier.PRO
    }
    selected_tier = tier_mapping.get(data.plan.lower(), PlanTier.STARTER)

    # 4. Create new User instance
    hashed = pwd_context.hash(data.password)
    
    new_user = User(
        name=data.name,
        email=data.email,
        hashed_password=hashed,
        is_active=True,
        
        # Profile Fields
        personal_whatsapp=data.personal_whatsapp,
        business_type=final_business_type,
        
        # Billing Fields
        plan_tier=selected_tier
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"✅ [Register Success] User created with ID: {new_user.id} | Tier: {selected_tier}")

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
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not pwd_context.verify(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": "valid-token", "token_type": "bearer"}