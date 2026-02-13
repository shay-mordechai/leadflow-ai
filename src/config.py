# src/config.py
import os
import boto3
import logging
from pydantic_settings import BaseSettings
from botocore.exceptions import ClientError
from typing import List, Dict

logger = logging.getLogger("Configuration")

# --- 1. Load Secrets Function ---
def load_ssm_secrets():
    if os.getenv("APP_ENV") != "production":
        return

    region = os.getenv("AWS_REGION", "eu-north-1")
    path = "/leadflow/prod/"
    
    logger.info(f"🔄 Attempting to load SSM secrets from {region}...")

    try:
        ssm = boto3.client("ssm", region_name=region)
        paginator = ssm.get_paginator('get_parameters_by_path')
        page_iterator = paginator.paginate(Path=path, Recursive=True, WithDecryption=True)
        
        count = 0
        for page in page_iterator:
            for param in page.get("Parameters", []):
                key = param["Name"].split("/")[-1]
                os.environ[key] = param["Value"]
                count += 1
        
        if count > 0:
            logger.info(f"✅ Successfully loaded {count} secrets from SSM.")
    except Exception as e:
        logger.warning(f"⚠ Failed to load SSM secrets: {e}")

# --- 2. Execute Loading Logic ---
load_ssm_secrets()

# --- 3. Define Settings Class ---
class Settings(BaseSettings):
    # --- Core Configuration ---
    APP_ENV: str = "development"
    SECRET_KEY: str = "temporary_dev_key" # Default for safety during boot
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    BASE_URL: str = "https://my-leads.app"
    ALLOWED_HOSTS: str = "*"
    
    # --- Database ---
    DATABASE_URL: str = "sqlite:///./leads.db"
    
    # --- Infrastructure ---
    S3_BUCKET_NAME: str = "leadflow-user-assets-prod"
    
    # --- Security ---
    ENCRYPTION_KEY: str = "" 
    
    # --- External AI APIs ---
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    
    # --- Telephony Providers ---
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    
    VONAGE_API_KEY: str = ""
    VONAGE_API_SECRET: str = ""
    VONAGE_APP_ID: str = ""
    VONAGE_PRIVATE_KEY_PATH: str = "/app/private.key"
    
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
        case_sensitive = True
        extra = "ignore" 

# --- 4. Validation Helper ---
def validate_config(s: Settings):
    """
    Checks for missing API keys and logs warnings for each service.
    """
    # Define groups of settings for clean reporting
    groups = {
        "AI (OpenAI/Google)": ["OPENAI_API_KEY", "GOOGLE_API_KEY"],
        "Telephony (Twilio)": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
        "Telephony (SignalWire)": ["SIGNALWIRE_PROJECT_ID", "SIGNALWIRE_AUTH_TOKEN", "SIGNALWIRE_SPACE_URL"],
        "WhatsApp (Meta)": ["META_ACCESS_TOKEN", "WHATSAPP_PHONE_ID"],
        "Email (SMTP)": ["MAIL_USERNAME", "MAIL_PASSWORD"],
        "Billing (Meshulam)": ["MESHULAM_PAGE_CODE", "MESHULAM_API_KEY"],
        "Security": ["ENCRYPTION_KEY"]
    }

    for group_name, keys in groups.items():
        missing = [k for k in keys if not getattr(s, k)]
        if missing:
            logger.warning(f"⚠ {group_name} credentials missing: {', '.join(missing)}. Feature will be disabled.")
        else:
            logger.info(f"✅ {group_name} configured correctly.")

# --- 5. Final Initialization ---
try:
    settings = Settings()
    # Run validation only in production to keep logs clean
    if settings.APP_ENV == "production":
        validate_config(settings)
except Exception as e:
    logger.critical(f"🔥 FATAL: Configuration failed. Error: {e}")
    raise