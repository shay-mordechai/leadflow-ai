import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from src.database.models import User, UserRole
from src.security.dependencies import get_current_user
from src.config import settings

router = APIRouter(prefix="/api/v1/storage", tags=["Storage"])

@router.get("/{file_path:path}")
async def get_local_file(file_path: str, current_user: User = Depends(get_current_user)):
    """
    Securely serves locally stored files with strict tenancy isolation.
    Users can only access files residing within their own directory, 
    unless they have ADMIN privileges.
    """
    base_dir = getattr(settings, 'STORAGE_BASE_PATH', '/app/storage')
    
    # SECURITY: Prevent path traversal attacks (Directory Traversal)
    safe_path = os.path.normpath(os.path.join(base_dir, file_path))
    if not safe_path.startswith(os.path.normpath(base_dir)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not os.path.exists(safe_path) or not os.path.isfile(safe_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # TENANCY & OWNERSHIP VALIDATION:
    # If the user is an ADMIN, grant access to any file.
    # Otherwise, ensure the file path contains the user's specific ID.
    if current_user.role != UserRole.ADMIN:
        user_id_str = str(current_user.id)
        # Expected path pattern containing user id (e.g. profiles/{user_id}/filename)
        if user_id_str not in safe_path:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Unauthorized: You do not own this file"
            )

    return FileResponse(safe_path)
