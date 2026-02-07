# src/config.py
import os
import boto3
import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger(\"Configuration\")

class Settings(BaseSettings):
    # Core
    SECRET_KEY: str
    ALGORITHM: str = \"HS256\"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str
    
    # Infrastructure
    S3_BUCKET_NAME: str = \"leadflow-user-assets-prod\"
    
    # External APIs
    OPENAI_API_KEY: str = \"\"
    GOOGLE_API_KEY: str = \"\"
    
    # Twilio
    TWILIO_ACCOUNT_SID: str = \"\"
    TWILIO_AUTH_TOKEN: str = \"\"
    
    # Meta / WhatsApp
    META_ACCESS_TOKEN: str = \"\"
    WHATSAPP_PHONE_ID: str = \"\"
    WHATSAPP_VERIFY_TOKEN: str = \"my_secure_token\"
    
    # Email
    MAIL_USERNAME: str = \"\"
    MAIL_PASSWORD: str = \"\"
    MAIL_FROM: str = \"noreply@leadflow.ai\"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = \"smtp.gmail.com\"
    
    # Feature Flags
    ENABLE_REAL_PHONE_PURCHASE: bool = True
    ALLOWED_HOSTS: str = \"*\"

    def __init__(self, **kwargs):
        # Runtime Injection from AWS SSM
        region = \"eu-north-1\"
        try:
            # Only attempt SSM if in production environment or forced
            if os.getenv(\"APP_ENV\") == \"production\" or True:
                ssm = boto3.client(\"ssm\", region_name=region)
                path = \"/leadflow/prod/\"
                
                paginator = ssm.get_paginator('get_parameters_by_path')
                page_iterator = paginator.paginate(Path=path, Recursive=True, WithDecryption=True)
                
                count = 0
                for page in page_iterator:
                    for param in page.get(\"Parameters\", []):
                        key = param[\"Name\"].replace(path, \"\")
                        os.environ[key] = param[\"Value\"]
                        count += 1
                
                logger.info(f\"✅ Loaded {count} secrets from SSM.\")
        except Exception as e:
            logger.warning(f\"⚠ SSM Load Skipped/Failed: {e}\")
            
        super().__init__(**kwargs)

settings = Settings()