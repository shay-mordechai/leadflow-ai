# src/security/dependencies.py
from typing import Optional
from contextvars import ContextVar
from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from src.database.session import get_db
from src.database.models import User
# Importing security config from your auth router
from src.routers.auth import SECRET_KEY, ALGORITHM 

# 1. Context Variable
# Holds the current User ID for the duration of the request.
_user_id_ctx: ContextVar[str] = ContextVar("user_id", default=None)

# Defines the endpoint for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_user_id() -> str:
    """
    Retrieves the current user ID from the context variable.
    """
    uid = _user_id_ctx.get()
    if uid is None:
        raise RuntimeError("Security Violation: No user context found.")
    return uid

async def get_current_user(
    request: Request, # Inject request to access cookies
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    # --- CLOUDFLARE SECURITY HEADERS ---
    # These headers are injected by Cloudflare. 
    # If running locally (no Cloudflare), they will be None.
    cf_ipcity: Optional[str] = Header(None, alias="cf-ipcity"),
    cf_ipcountry: Optional[str] = Header(None, alias="cf-ipcountry")
) -> User:
    """
    Dependency to validate the current user.
    1. Extracts token from Cookie (Dashboard) or Header (API).
    2. Decodes JWT and validates user in DB.
    3. Performs 'Impossible Travel' check using Cloudflare headers.
    """
    
    # --- TOKEN EXTRACTION ---
    # Try to get the token from the Cookie (set during login)
    actual_token = request.cookies.get("access_token")
    
    # Fallback: if no cookie, try the Authorization Header (provided by oauth2_scheme)
    if not actual_token:
        actual_token = token

    if not actual_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --- REAL JWT VALIDATION ---
    try:
        # Decode the token using our secret key and algorithm
        payload = jwt.decode(actual_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Could not validate credentials"
        )

    # Fetch user from Database
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --- LOCATION SECURITY CHECK (IMPOSSIBLE TRAVEL) ---
    # [Image of Cloudflare geolocation headers flow]
    # Logic: If the user has a stored 'last_known_city' in the DB, 
    # and the current request comes from a DIFFERENT city, we block access.
    
    if cf_ipcity and user.last_known_city:
        # Normalize strings to avoid case sensitivity issues
        if cf_ipcity.lower() != user.last_known_city.lower():
            print(f"SECURITY ALERT: User {user.email} moved from {user.last_known_city} to {cf_ipcity}. Blocking access.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Location changed. Please login again for security verification.",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    # Note: We do NOT update the DB here (GET request). 
    # The DB update should happen in the POST /login endpoint.

    # Set the global context variable for logging/auditing
    _user_id_ctx.set(str(user.id))
    
    return user