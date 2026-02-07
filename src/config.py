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
    
    # External APIs
    OPENAI_API_KEY: str = \"\"
    GOOGLE_API_KEY: str = \"\"
    TWILIO_ACCOUNT_SID: str = \"\"
    TWILIO_AUTH_TOKEN: str = \"\"
    
    # Webhooks & Security
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
            ssm = boto3.client(\"ssm\", region_name=region)
            path = \"/leadflow/prod/\"
            response = ssm.get_parameters_by_path(
                Path=path, Recursive=True, WithDecryption=True
            )
            
            for param in response.get(\"Parameters\", []):
                key = param[\"Name\"].replace(path, \"\")
                if key not in os.environ:
                    os.environ[key] = param[\"Value\"]
            
            logger.info(f\"✅ Successfully loaded {len(response.get('Parameters', []))} secrets from SSM.\")
        except Exception as e:
            logger.warning(f\"⚠ SSM Load Failed: {e}\")
            
        super().__init__(**kwargs)

settings = Settings()