from typing import Optional
from contextvars import ContextVar
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from src.database.session import get_db
from src.database.models import User

# 1. Context Variable
# Holds the current User ID for the duration of the request.
# Useful for logging and auditing without passing user_id everywhere.
_user_id_ctx: ContextVar[str] = ContextVar("user_id", default=None)

# Defines the endpoint that returns the JWT token (for Swagger UI auth button)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_user_id() -> str:
    """
    Retrieves the current user ID from the context variable.
    Raises RuntimeError if accessed outside a secured endpoint.
    """
    uid = _user_id_ctx.get()
    if uid is None:
        raise RuntimeError("Security Violation: No user context found.")
    return uid

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to validate the current user.
    1. Validates the token (Currently a mock implementation).
    2. Fetches user from DB.
    3. Sets the user ID in the context variable.
    """
    
    # --- MOCK AUTHENTICATION LOGIC ---
    # TODO: Replace this block with real JWT decoding (PyJWT)
    # For development: We accept ANY token and return the first user found.
    
    # Try to find a specific admin user for testing, or fallback to the first user
    user = db.query(User).filter(User.email == "admin@test.com").first()
    
    if not user:
        user = db.query(User).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - No users in DB",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # ---------------------------------

    # Set the global context variable
    _user_id_ctx.set(str(user.id))
    
    return user