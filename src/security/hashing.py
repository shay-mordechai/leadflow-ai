# src/security/hashing.py
from passlib.context import CryptContext
import hashlib

# Initialize Password Context using BCrypt.
# Note: BCrypt is robust but has a known limitation of 72 bytes for input.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _pre_hash(secret: str) -> str:
    """
    Internal helper: Pre-hashes inputs using SHA-256.

    Why this is necessary:
    1. BCrypt truncates inputs longer than 72 bytes, which reduces entropy for long API keys.
    2. SHA-256 converts any input length into a fixed 64-character hex string.
    3. This ensures the input fits safely within BCrypt's limits while maintaining high security.
    """
    # Returns a 64-char hex string (e.g., 'a5d3...')
    return hashlib.sha256(secret.encode('utf-8')).hexdigest()

def get_hash(secret: str) -> str:
    """
    Generates a secure BCrypt hash of the pre-hashed secret.
    Used for storing API keys and passwords securely in the database.
    """
    if not secret:
        raise ValueError("Secret cannot be empty.")

    safe_secret = _pre_hash(secret)
    return pwd_context.hash(safe_secret)

def verify_hash(plain_secret: str, hashed_secret: str) -> bool:
    """
    Verifies a plain-text secret against a stored hash.
    First applies the same pre-hashing (SHA-256), then verifies via BCrypt.
    """
    if not plain_secret or not hashed_secret:
        return False

    safe_secret = _pre_hash(plain_secret)
    return pwd_context.verify(safe_secret, hashed_secret)

# --- ALIAS FOR COMPATIBILITY ---
# This ensures that routers calling 'verify_password' still work correctly
verify_password = verify_hash