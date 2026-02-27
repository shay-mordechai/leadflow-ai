# src/config.py
import os
import boto3
import logging
import requests
from pydantic_settings import BaseSettings
from botocore.exceptions import ClientError
from typing import List, Dict, Optional

logger = logging.getLogger("Configuration")

# --- 1. Load AWS Configuration Logic ---
def load_aws_configurations():
    """
    Attempts to load configuration and secrets from AWS SSM Parameter Store.
    Uses IMDSv2 to detect if running on EC2 and fetch the region automatically.
    """
    # Fast fail if explicitly set to development to save boot time locally
    if os.getenv("APP_ENV") == "development":
        return

    try:
        # Step 1: Request IMDSv2 Token (1-second timeout to fail fast locally)
        token_url = "http://169.254.169.254/latest/api/token"
        headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        token_response = requests.put(token_url, headers=headers, timeout=1)
        
        if token_response.status_code != 200:
            return # Not on AWS EC2
            
        # Sanitize response to remove trailing newlines
        token = token_response.text.strip()

        # Step 2: Get Current Region using the Token
        region_url = "http://169.254.169.254/latest/meta-data/placement/region"
        region_headers = {"X-aws-ec2-metadata-token": token}
        region_response = requests.get(region_url, headers=region_headers, timeout=1)
        region = region_response.text.strip()

        logger.info(f"☁️ Detected AWS Environment (Region: {region}). Initializing SSM...")

        # Step 3: Initialize Boto3 SSM Client
        ssm = boto3.client('ssm', region_name=region)
        
        # Step 4: Determine Path prefix (Configurable for staging/prod)
        ssm_path = os.getenv("SSM_PATH_PREFIX", "/leadflow/prod/")
        if not ssm_path.endswith("/"):
            ssm_path += "/"

        # Step 5: Fetch Parameters with Pagination
        paginator = ssm.get_paginator('get_parameters_by_path')
        page_iterator = paginator.paginate(
            Path=ssm_path,
            Recursive=True,
            WithDecryption=True
        )

        count = 0
        for page in page_iterator:
            for param in page.get("Parameters", []):
                # Extract the clean environment variable name from the path
                key = param["Name"].split("/")[-1]
                os.environ[key] = param["Value"]
                count += 1
        
        if count > 0:
            logger.info(f"✅ Successfully loaded {count} secrets from AWS SSM Path: {ssm_path}")

    except requests.exceptions.RequestException:
        # Network error implies we are local and the IMDSv2 endpoint is unreachable
        logger.info("ℹ️ Local environment detected. Skipping AWS SSM load.")
    except ClientError as e:
        logger.error(f"⛔ AWS SSM Client Error (Check IAM Policies): {e}")
    except Exception as e:
        logger.warning(f"⚠️ Unexpected error loading SSM secrets: {e}. Falling back to local env.")

# --- 2. Execute Loading Logic ---
# This runs before the Settings class is instantiated so Pydantic can read the injected os.environ
load_aws_configurations()

# --- 3. Define Settings Class ---
class Settings(BaseSettings):
    # --- Core Configuration ---
    APP_NAME: str = "LeadFlow AI"
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
    TWILIO_WHATSAPP_NUMBER: str = ""  # NEW: The WhatsApp sender number from Twilio
    
    VONAGE_API_KEY: str = ""
    VONAGE_API_SECRET: str = ""
    VONAGE_APP_ID: str = ""
    VONAGE_PRIVATE_KEY_PATH: str = "/app/private.key"
    
    SIGNALWIRE_PROJECT_ID: str = ""
    SIGNALWIRE_AUTH_TOKEN: str = ""
    SIGNALWIRE_SPACE_URL: str = ""
    
    # --- Meta / WhatsApp (Kept for backwards compatibility if needed) ---
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

    SENTRY_DSN: Optional[str] = None
    
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
        "Telephony (Twilio)": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_NUMBER"],
        "Telephony (SignalWire)": ["SIGNALWIRE_PROJECT_ID", "SIGNALWIRE_AUTH_TOKEN", "SIGNALWIRE_SPACE_URL"],
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