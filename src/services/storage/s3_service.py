# src/services/storage/s3_service.py
import boto3
import logging
from botocore.exceptions import ClientError
from src.config import settings
from typing import Optional

logger = logging.getLogger("S3Service")

class S3Service:
    """
    Handles secure file operations with Amazon S3.
    Uses IAM Roles in production or environment keys in dev.
    """
    def __init__(self):
        self.bucket_name = getattr(settings, 'S3_BUCKET_NAME', 'myleads-kyc-storage')
        self.s3_client = boto3.client('s3', region_name=getattr(settings, 'AWS_REGION', 'eu-north-1'))

    def upload_fileobj(self, file_obj, object_name: str, content_type: str) -> bool:
        """
        Uploads a file object (from FastAPI) directly to S3.
        """
        try:
            logger.info(f"📤 Uploading to S3: {object_name} in bucket {self.bucket_name}")
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_name,
                ExtraArgs={'ContentType': content_type}
            )
            return True
        except ClientError as e:
            logger.error(f"❌ S3 Upload Error: {e}")
            return False

    def generate_presigned_url(self, object_name: str, expiration: int = 3600) -> Optional[str]:
        """
        Generates a temporary, secure URL for viewing a private file.
        Default expiration: 1 hour.
        """
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"❌ Failed to generate presigned URL: {e}")
            return None

# Singleton instance
s3_service = S3Service()