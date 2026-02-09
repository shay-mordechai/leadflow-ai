# src/config.py
# src/config.py
import os
import boto3
import logging
from pydantic_settings import BaseSettings
from botocore.exceptions import ClientError

logger = logging.getLogger("Configuration")

# --- 1. Load Secrets Function (Runs BEFORE Pydantic) ---
def load_ssm_secrets():
    """
    Attempts to load secrets from AWS SSM Parameter Store into os.environ.
    This must run BEFORE the Settings class is instantiated.
    """
    # Only run in production or if explicitly requested
    # We check for 'production' string to avoid accidental runs on local dev
    if os.getenv("APP_ENV") != "production":
        return

    region = os.getenv("AWS_REGION", "eu-north-1")
    path = "/leadflow/prod/"
    
    logger.info(f"🔄 Attempting to load SSM secrets from {region}...")

    try:
        # We DO NOT check for AWS_ACCESS_KEY_ID because EC2 Roles don't use it.
        # We let boto3 try to find credentials automatically via IAM Role.
        ssm = boto3.client("ssm", region_name=region)
        
        paginator = ssm.get_paginator('get_parameters_by_path')
        page_iterator = paginator.paginate(
            Path=path, 
            Recursive=True, 
            WithDecryption=True
        )
        
        count = 0
        for page in page_iterator:
            for param in page.get("Parameters", []):
                # Logic: Convert /leadflow/prod/SECRET_KEY -> SECRET_KEY
                key = param["Name"].split("/")[-1]
                value = param["Value"]
                
                # Inject into environment variable so Pydantic can find it later
                os.environ[key] = value
                count += 1
        
        if count > 0:
            logger.info(f"✅ Successfully loaded {count} secrets from SSM.")
        else:
            logger.warning("⚠ Connected to SSM but found 0 parameters.")

    except ClientError as e:
        # Permissions issue (IAM Role might be missing SSM read access)
        logger.warning(f"⚠ SSM Permission Error: {e}")
    except Exception as e:
        # Network or other issue
        logger.warning(f"⚠ Failed to load SSM secrets: {e}")

# --- 2. Execute Loading Logic ---
load_ssm_secrets()

# --- 3. Define Settings Class ---
class Settings(BaseSettings):
    # --- Core Configuration ---
    APP_ENV: str = "development"
    SECRET_KEY: str  # Will be populated from SSM
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    BASE_URL: str = "https://my-leads.app"
    ALLOWED_HOSTS: str = "*"
    
    # --- Database ---
    DATABASE_URL: str # Will be populated from SSM
    
    # --- Infrastructure ---
    S3_BUCKET_NAME: str = "leadflow-user-assets-prod"
    
    # --- Security ---
    ENCRYPTION_KEY: str = "" 
    
    # --- External AI APIs ---
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    
    # --- Telephony Providers ---
    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    
    # Vonage (Critical Fix: Added missing fields)
    VONAGE_API_KEY: str = ""
    VONAGE_API_SECRET: str = ""
    VONAGE_APP_ID: str = ""
    VONAGE_PRIVATE_KEY_PATH: str = "/app/private.key" # Default path inside container
    
    # SignalWire (Critical Fix: Added missing fields)
    SIGNALWIRE_PROJECT_ID: str = ""
    SIGNALWIRE_AUTH_TOKEN: str = ""
    SIGNALWIRE_SPACE_URL: str = ""
    
    # --- Meta / WhatsApp ---
    META_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "my_secure_token"
    
    # --- Email (SMTP) ---
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@leadflow.ai"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp-relay.brevo.com"

    # --- Billing (Meshulam) ---
    MESHULAM_PAGE_CODE: str = ""
    MESHULAM_API_KEY: str = ""

    # --- Feature Flags ---
    ENABLE_REAL_PHONE_PURCHASE: bool = True

    class Config:
        # Even though you don't use .env, this is required for Pydantic 
        # to know it's allowed to read from os.environ (which SSM populated)
        case_sensitive = True
        extra = "ignore" 

# Singleton Instance
try:
    settings = Settings()
except Exception as e:
    logger.critical(f"🔥 FATAL: Configuration failed. Missing environment variables? Error: {e}")
    raise