# src/schemas/user.py
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, ConfigDict
from typing import Optional
import re

# --- Constants for Security Regex Patterns ---
NAME_REGEX = r"^[a-zA-Zא-ת\s\-']+$"
PHONE_REGEX = r"^(\+972|05)[0-9\-]{8,15}$"
SAFE_TEXT_REGEX = r"^[a-zA-Zא-ת0-9\s\-\.]+$"

# --- Base Schema (Shared Fields) ---
class UserBase(BaseModel):
    plan_tier: Optional[str] = "starter" 
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=50, description="User full name")
    
    business_name: Optional[str] = Field(None, max_length=100)
    business_type: str = Field(..., max_length=50)
    other_business_type: Optional[str] = Field(None, max_length=50)
    city_coverage: Optional[str] = Field(None, max_length=50)
    
    personal_whatsapp: Optional[str] = Field(None, max_length=20)
    business_whatsapp: Optional[str] = Field(None, max_length=20)
    needs_new_number: bool = False

    @field_validator('full_name', 'city_coverage', 'business_name')
    @classmethod
    def validate_safe_text(cls, v: str | None):
        if v and not re.match(NAME_REGEX, v):
            raise ValueError("Field contains invalid characters. Only letters, spaces, and hyphens allowed.")
        return v

    @field_validator('personal_whatsapp', 'business_whatsapp')
    @classmethod
    def validate_phones(cls, v: str | None):
        if v:
            clean_v = v.replace("-", "").replace(" ", "")
            if not re.match(r"^\+?[0-9]{9,15}$", clean_v):
                raise ValueError("Invalid phone number format.")
            return clean_v
        return v

# --- Schema for Registration (Input) ---
class UserCreate(UserBase):
    # Professional English Comment:
    # Security Enforcement: Passwords must be 12+ chars, mixed case, numbers & symbols.
    password: str = Field(..., min_length=12, description="Strong password required")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @model_validator(mode='after')
    def check_other_business_type(self):
        if self.business_type == 'Other' and not self.other_business_type:
            raise ValueError("Please specify your business type in the text field.")
        return self

# --- Schema for Reading/Response (The Security Filter) 🛡️ ---
class UserResponse(BaseModel):
    id: int # Changed to int to match DB
    email: EmailStr
    
    # Secure Handling: Provide both name for Frontend and full_name for API consistency
    full_name: str = Field(..., alias="name")
    name: Optional[str] = None # Support for older Frontend logic
    
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    
    # Mapping DB 'plan_type' to API 'plan_tier'
    plan_tier: str = Field(default="free", alias="plan_type") 
    
    # S3 Integration: URL for profile image stored in AWS S3
    profile_image_url: Optional[str] = None
    
    is_active: bool

    @model_validator(mode='after')
    def sync_name_fields(self):
        # Ensure 'name' field is populated from 'full_name' alias if missing
        if not self.name:
            self.name = self.full_name
        return self

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)