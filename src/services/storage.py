import boto3
import logging
from botocore.exceptions import ClientError
from src.config import settings

logger = logging.getLogger("StorageService")

# Initialize S3 Client using IAM Role credentials
s3_client = boto3.client('s3', region_name='eu-north-1')
BUCKET_NAME = "leadflow-user-assets-shay"

class StorageService:
    """
    AWS S3 Storage Service for LeadFlow.
    Handles file uploads and secure pre-signed URL generation.
    """
    
    def get_upload_params(self, file_name: str, user_id: int, expiration=3600):
        """
        Generates a Pre-signed POST URL for direct browser-to-S3 upload.
        This reduces server load as files don't pass through the Backend.
        """
        object_name = f"profiles/{user_id}/{file_name}"
        try:
            response = s3_client.generate_presigned_post(
                Bucket=BUCKET_NAME,
                Key=object_name,
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"Failed to generate S3 upload URL: {e}")
            return None

    def get_file_url(self, object_key: str, expiration=3600):
        """
        Generates a temporary secure GET URL for viewing private S3 objects.
        """
        try:
            return s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': BUCKET_NAME, 'Key': object_key},
                ExpiresIn=expiration
            )
        except ClientError as e:
            logger.error(f"Failed to generate S3 download URL: {e}")
            return None

storage_service = StorageService()