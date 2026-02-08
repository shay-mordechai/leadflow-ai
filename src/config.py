# src/config.py
import os
import boto3
import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger("Configuration")

class Settings(BaseSettings):
    # --- Core Configuration ---
    APP_ENV: str = "development"  # 'production', 'testing', or 'development'
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    BASE_URL: str = "https://my-leads.app"  # Required for Webhooks (Twilio/Stripe/Meshulam)
    ALLOWED_HOSTS: str = "*"
    
    # --- Database ---
    DATABASE_URL: str
    
    # --- Infrastructure ---
    S3_BUCKET_NAME: str = "leadflow-user-assets-prod"
    
    # --- Security (PII Encryption) ---
    # CRITICAL: Must be a 32-byte url-safe base64-encoded string.
    ENCRYPTION_KEY: str = "" 
    
    # --- External AI APIs ---
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    
    # --- Telephony Providers ---
    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    
    # Plivo
    PLIVO_AUTH_ID: str = ""
    PLIVO_AUTH_TOKEN: str = ""

    # Vonage
    VONAGE_API_KEY: str = ""
    VONAGE_API_SECRET: str = ""

    # SignalWire (Alternative Provider)
    SIGNALWIRE_PROJECT_ID: str = ""
    SIGNALWIRE_AUTH_TOKEN: str = ""
    SIGNALWIRE_SPACE_URL: str = ""
    
    # --- Meta / WhatsApp Cloud API ---
    META_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "my_secure_token"
    
    # --- Email (SMTP) ---
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@leadflow.ai"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"

    # --- Billing / Payments (Meshulam) ---
    MESHULAM_PAGE_CODE: str = ""
    MESHULAM_API_KEY: str = ""
    
    # --- Feature Flags ---
    ENABLE_REAL_PHONE_PURCHASE: bool = True

    def __init__(self, **kwargs):
        """
        Initializes settings. 
        If in PRODUCTION, attempts to inject secrets from AWS Systems Manager (SSM).
        """
        super().__init__(**kwargs)
        
        # Runtime Injection from AWS SSM
        region = "eu-north-1"
        try:
            # Only attempt SSM if in production environment or forced via flag
            # The 'or True' ensures it attempts retrieval, but the try/except protects CI/CD
            if os.getenv("APP_ENV") == "production" or True:
                # We check if we have AWS credentials before calling boto3 to avoid hanging/crashing in CI
                if os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE"):
                    ssm = boto3.client("ssm", region_name=region)
                    path = "/leadflow/prod/"
                    
                    paginator = ssm.get_paginator('get_parameters_by_path')
                    page_iterator = paginator.paginate(Path=path, Recursive=True, WithDecryption=True)
                    
                    count = 0
                    for page in page_iterator:
                        for param in page.get("Parameters", []):
                            key = param["Name"].replace(path, "")
                            # Update environment variable so Pydantic can read it if re-instantiated
                            os.environ[key] = param["Value"]
                            # Also update the current instance attributes dynamically
                            if hasattr(self, key):
                                setattr(self, key, param["Value"])
                            count += 1
                    
                    logger.info(f"✅ Loaded {count} secrets from SSM.")
        except Exception as e:
            # This is normal in CI/Test environments where AWS credentials might be missing
            logger.warning(f"⚠ SSM Load Skipped/Failed: {e}")

# Singleton Instance
settings = Settings()