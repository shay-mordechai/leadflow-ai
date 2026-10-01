import os
import shutil
import logging
from typing import Optional
from src.config import settings

logger = logging.getLogger("LocalStorageService")

class LocalStorageService:
    """
    Handles local file storage on bare-metal Hetzner server.
    Replaces AWS S3 to eliminate cloud infrastructure costs.
    """
    def __init__(self):
        # Base directory inside container
        self.base_dir = getattr(settings, 'STORAGE_BASE_PATH', '/app/storage')
        self.base_url = getattr(settings, 'BASE_URL', 'https://my-leads.app').rstrip('/')
        os.makedirs(self.base_dir, exist_ok=True)

    def upload_fileobj(self, file_obj, object_name: str, content_type: Optional[str] = None) -> bool:
        """
        Saves an uploaded file object directly to the local filesystem.
        """
        try:
            target_path = os.path.join(self.base_dir, object_name)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # Ensure read pointer is at start
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)

            with open(target_path, "wb") as destination:
                shutil.copyfileobj(file_obj, destination)

            logger.info(f"💾 File stored locally: {target_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Local Storage Upload Error: {e}")
            return False

    def generate_presigned_url(self, object_name: str, expiration: int = 3600) -> Optional[str]:
        """
        Returns the public URL for the stored file via our protected gateway.
        """
        clean_object_name = object_name.lstrip('/')
        return f"{self.base_url}/api/v1/storage/{clean_object_name}"

# Drop-in singleton replacement (backward compatible with existing imports)
s3_service = LocalStorageService()
