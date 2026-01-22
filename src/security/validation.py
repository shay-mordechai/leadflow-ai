# src/security/validation.py
import re
import bleach
from typing import Tuple, Optional
from datetime import datetime, timedelta
from jose import jwt
from src.config import settings

# --- JWT TOKEN GENERATION ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a JWT Token signed with the server's SECRET_KEY.
    Used for user authentication after OTP verification.
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Default expiration set in config (usually 24 hours)
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Standard JWT claims
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt

# --- INPUT SANITIZATION ---
class SecurityValidator:
    """
    OWASP Input Validation & Sanitization Utility.
    """

    # Strict Regex for Israeli Mobile Numbers (05X-XXXXXXX or +972-5X-XXXXXXX)
    # Prevents Injection via phone fields and ensures data integrity.
    ISRAEL_PHONE_REGEX = re.compile(r'^(?:\+972|0)(5[0-248-9])\-?\d{7}$')

    @staticmethod
    def sanitize_text(text: Optional[str]) -> str:
        """
        Sanitizes input strings to prevent Stored Cross-Site Scripting (XSS).
        Removes all HTML tags and dangerous attributes.
        """
        if not text:
            return ""

        # 'strip=True' removes the tags entirely (e.g. <script>alert(1)</script> -> alert(1))
        # This renders the payload inert in an HTML context.
        cleaned = bleach.clean(text, tags=[], attributes={}, strip=True)
        return cleaned.strip()

    @staticmethod
    def validate_israeli_phone(phone: str) -> Tuple[bool, str]:
        """
        Validates and normalizes phone numbers.
        Returns: (is_valid, normalized_number)
        """
        if not phone:
            return False, ""

        # Remove common separators (dashes, spaces)
        clean_num = re.sub(r'[\s\-]', '', phone)

        match = SecurityValidator.ISRAEL_PHONE_REGEX.match(clean_num)
        if match:
            # Normalize to 05X format for DB consistency
            if clean_num.startswith('+972'):
                clean_num = '0' + clean_num[4:]
            return True, clean_num

        return False, ""