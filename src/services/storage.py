# src/services/storage.py
import boto3
import logging
from botocore.exceptions import ClientError
from src.config import settings

logger = logging.getLogger("StorageService")

# Initialize S3 Client (IAM Role)
s3_client = boto3.client('s3', region_name='eu-north-1')

class StorageService:
    def get_upload_params(self, file_name: str, user_id: str, expiration=3600):
        object_name = f"profiles/{user_id}/{file_name}"
        try:
            response = s3_client.generate_presigned_post(
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_name,
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"Failed to generate S3 upload URL: {e}")
            return None

    def get_file_url(self, object_key: str, expiration=3600):
        try:
            return s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.S3_BUCKET_NAME, 'Key': object_key},
                ExpiresIn=expiration
            )
        except ClientError as e:
            logger.error(f"Failed to generate S3 download URL: {e}")
            return None

storage_service = StorageService()