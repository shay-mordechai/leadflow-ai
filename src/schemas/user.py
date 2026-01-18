# src/shcemas/user.py
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional
import re

# --- Constants for Security Regex Patterns ---
# Name: Allows English, Hebrew, spaces, hyphens, and apostrophes.
NAME_REGEX = r"^[a-zA-Zא-ת\s\-']+$"

# Phone: Basic International or Israeli format.
PHONE_REGEX = r"^(\+972|05)[0-9\-]{8,15}$"

# Safe Text: Alphanumeric, spaces, hyphens, dots. Prevents Script tags (<>).
SAFE_TEXT_REGEX = r"^[a-zA-Zא-ת0-9\s\-\.]+$"

# --- Base Schema (Shared Fields) ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=50, description="User full name")
    
    # Business Details
    business_name: Optional[str] = Field(None, max_length=100)
    business_type: str = Field(..., max_length=50)  # From Select options
    other_business_type: Optional[str] = Field(None, max_length=50)
    city_coverage: Optional[str] = Field(None, max_length=50)
    
    # Contact Details
    personal_whatsapp: Optional[str] = Field(None, max_length=20)
    business_whatsapp: Optional[str] = Field(None, max_length=20)
    needs_new_number: bool = False

    # --- Validators ---

    @field_validator('full_name', 'city_coverage', 'business_name')
    @classmethod
    def validate_safe_text(cls, v: str | None):
        """
        Security Validator:
        Ensures text fields do not contain special characters that could be used for XSS.
        """
        if v and not re.match(NAME_REGEX, v):
            raise ValueError("Field contains invalid characters. Only letters, spaces, and hyphens allowed.")
        return v

    @field_validator('personal_whatsapp', 'business_whatsapp')
    @classmethod
    def validate_phones(cls, v: str | None):
        """
        Phone Validator:
        Strips format characters and checks for valid digit length.
        """
        if v:
            # Sanitize: Remove dashes and spaces
            clean_v = v.replace("-", "").replace(" ", "")
            if not re.match(r"^\+?[0-9]{9,15}$", clean_v):
                raise ValueError("Invalid phone number format.")
            return clean_v # Return the clean number to DB
        return v

    @field_validator('other_business_type')
    @classmethod
    def validate_strict_text(cls, v: str | None):
        """
        Strict Validator for Free Text:
        Prevents injection attacks in the 'Other' field.
        """
        if v:
            if not re.match(SAFE_TEXT_REGEX, v):
                raise ValueError("Field contains invalid characters.")
            # Double safety: Remove HTML tags
            v = re.sub(r'[<>]', '', v)
        return v

# --- Schema for Registration (Input) ---
class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Plain text password")

    @model_validator(mode='after')
    def check_other_business_type(self):
        """
        Logic Validator:
        If 'business_type' is 'Other', then 'other_business_type' must be provided.
        """
        b_type = self.business_type
        other_type = self.other_business_type

        if b_type == 'Other' and not other_type:
            raise ValueError("Please specify your business type in the text field.")
        
        return self

# --- Schema for Reading/Response (Output) ---
class UserRead(UserBase):
    id: int
    is_active: bool
    plan_tier: str = "Starter"

    class Config:
        # Pydantic V2 configuration to allow reading from ORM objects
        from_attributes = True