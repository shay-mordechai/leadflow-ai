# src/config.py
import os
import stat
import boto3
import logging
import requests
import json
import time
from pydantic_settings import BaseSettings, SettingsConfigDict
from botocore.exceptions import ClientError
from typing import List, Dict, Optional
from cryptography.fernet import Fernet

logger = logging.getLogger("Configuration")

# --- SSM CACHING MECHANISM (ENCRYPTED) ---
# Prevents API spamming to AWS if the server restart-loops
SSM_CACHE_FILE = "/tmp/ssm_secrets_cache.enc"
SSM_CACHE_KEY_FILE = "/tmp/ssm_cache.key"
CACHE_EXPIRATION_SECONDS = 3600  # 1 hour cache

def _get_or_create_cache_key() -> bytes:
    """
    Tier 2 Security: Generates or retrieves a local encryption key.
    Enforces strict file permissions (600) so only the owner can read it.
    """
    if os.path.exists(SSM_CACHE_KEY_FILE):
        with open(SSM_CACHE_KEY_FILE, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        # Open file descriptor with strict permissions
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        # stat.S_IRUSR | stat.S_IWUSR equals to 0o600 (Owner Read/Write only)
        with os.fdopen(os.open(SSM_CACHE_KEY_FILE, flags, stat.S_IRUSR | stat.S_IWUSR), 'wb') as f:
            f.write(key)
        return key

def load_aws_configurations():
    if os.getenv("APP_ENV") == "development":
        return

    # 1. Check local ENCRYPTED cache first
    try:
        if os.path.exists(SSM_CACHE_FILE):
            file_age = time.time() - os.path.getmtime(SSM_CACHE_FILE)
            if file_age < CACHE_EXPIRATION_SECONDS:
                key = _get_or_create_cache_key()
                fernet = Fernet(key)
                
                with open(SSM_CACHE_FILE, 'rb') as f:
                    encrypted_data = f.read()
                    
                decrypted_data = fernet.decrypt(encrypted_data)
                cached_secrets = json.loads(decrypted_data.decode('utf-8'))
                
                for k, v in cached_secrets.items():
                    os.environ[k] = v
                    
                logger.info(f"⚡ Loaded secrets from ENCRYPTED local cache (Age: {int(file_age)}s).")
                return
    except Exception as e:
        logger.warning(f"Failed to read encrypted SSM cache: {e}")

    # 2. Fetch from AWS if no valid cache exists
    try:
        token_url = "http://169.254.169.254/latest/api/token"
        headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        token_response = requests.put(token_url, headers=headers, timeout=1)
        if token_response.status_code != 200: return 
            
        token = token_response.text.strip()
        region_url = "http://169.254.169.254/latest/meta-data/placement/region"
        region_headers = {"X-aws-ec2-metadata-token": token}
        region_response = requests.get(region_url, headers=region_headers, timeout=1)
        region = region_response.text.strip()

        logger.info(f"☁️ Fetching fresh secrets from AWS SSM (Region: {region})...")
        ssm = boto3.client('ssm', region_name=region)
        ssm_path = os.getenv("SSM_PATH_PREFIX", "/leadflow/prod/")
        if not ssm_path.endswith("/"): ssm_path += "/"

        paginator = ssm.get_paginator('get_parameters_by_path')
        page_iterator = paginator.paginate(Path=ssm_path, Recursive=True, WithDecryption=True)

        fetched_secrets = {}
        for page in page_iterator:
            for param in page.get("Parameters", []):
                key = param["Name"].split("/")[-1]
                value = param["Value"]
                os.environ[key] = value
                fetched_secrets[key] = value
        
        # 3. Encrypt and save to cache
        if fetched_secrets:
            try:
                key = _get_or_create_cache_key()
                fernet = Fernet(key)
                
                json_data = json.dumps(fetched_secrets).encode('utf-8')
                encrypted_data = fernet.encrypt(json_data)
                
                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                try:
                    # Remove old file if exists to recreate with strict permissions
                    if os.path.exists(SSM_CACHE_FILE):
                        os.remove(SSM_CACHE_FILE)
                    with os.fdopen(os.open(SSM_CACHE_FILE, flags, stat.S_IRUSR | stat.S_IWUSR), 'wb') as f:
                        f.write(encrypted_data)
                except Exception as io_err:
                    # Fallback if file exists and we can't remove it
                    with open(SSM_CACHE_FILE, 'wb') as f:
                        f.write(encrypted_data)
                    os.chmod(SSM_CACHE_FILE, stat.S_IRUSR | stat.S_IWUSR)
                 
                logger.info(f"✅ Successfully loaded and ENCRYPTED {len(fetched_secrets)} secrets from AWS SSM.")
            except Exception as ce:
                 logger.warning(f"Could not write encrypted SSM cache file: {ce}")

    except requests.exceptions.RequestException:
        logger.info("ℹ️ Local environment detected. Skipping AWS SSM load.")
    except ClientError as e:
        logger.error(f"⛔ AWS SSM Client Error: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Unexpected error loading SSM secrets: {e}")

load_aws_configurations()

class Settings(BaseSettings):
    # --- Core Configuration ---
    APP_NAME: str = "LeadFlow AI"
    APP_ENV: str = "development"
    SECRET_KEY: str = "temporary_dev_key" 
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    BASE_URL: str = "https://my-leads.app"
    ALLOWED_HOSTS: str = "*"
    
    # --- Database & Queues (NEW: REDIS) ---
    # Using absolute path for Docker reliability
    DATABASE_URL: str = "sqlite:////app/data/leads.db"
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    
    # --- Infrastructure ---
    S3_BUCKET_NAME: str = "leadflow-user-assets-prod"
    ENCRYPTION_KEY: str = "" 
    
    # --- External AI APIs ---
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    
    # --- Telephony Providers ---
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""
    
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

    # --- Analytics (PostHog) ---
    NEXT_PUBLIC_POSTHOG_HOST: str = "https://eu.i.posthog.com"
    NEXT_PUBLIC_POSTHOG_KEY: str = ""
    POSTHOG_PROJECT_ID: str = ""

    ENABLE_REAL_PHONE_PURCHASE: bool = True
    SENTRY_DSN: Optional[str] = None
    
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore", env_file=".env")

def validate_config(s: Settings):
    if not (s.GOOGLE_API_KEY or s.OPENAI_API_KEY):
        logger.warning("❌ CRITICAL: No AI Engines configured.")

try:
    settings = Settings()
    if settings.APP_ENV == "production": validate_config(settings)
except Exception as e:
    logger.critical(f"🔥 FATAL: Configuration failed. Error: {e}")
    raise