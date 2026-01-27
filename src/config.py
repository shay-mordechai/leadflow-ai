# src/config.py
import os
import logging
import requests
import boto3
from typing import Any, List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# --- Logging Setup for Configuration Phase ---
logger = logging.getLogger("Configuration")
logging.basicConfig(level=logging.INFO)

# --- AWS & Configuration Loading Logic ---

def load_aws_configurations():
    try:
        token_url = "http://169.254.169.254/latest/api/token"
        headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        token_response = requests.put(token_url, headers=headers, timeout=1)
        if token_response.status_code != 200: return  
        token = token_response.text

        region_url = "http://169.254.169.254/latest/meta-data/placement/region"
        region_headers = {"X-aws-ec2-metadata-token": token}
        region_response = requests.get(region_url, headers=region_headers, timeout=1)
        region = region_response.text

        logger.info(f"☁️ Detected AWS Environment (Region: {region}). Initializing SSM...")

        ssm = boto3.client('ssm', region_name=region)
        ssm_path = "/leadflow/prod/" 

        paginator = ssm.get_paginator('get_parameters_by_path')
        page_iterator = paginator.paginate(Path=ssm_path, Recursive=True, WithDecryption=True)

        params_loaded = 0
        for page in page_iterator:
            for param in page.get('Parameters', []):
                key = param['Name'].split("/")[-1]
                value = param['Value']
                os.environ[key] = value
                params_loaded += 1
        
        logger.info(f"🔐 Successfully loaded {params_loaded} secrets from AWS SSM.")

    except Exception as e:
        logger.warning(f"⚠️ AWS SSM Load Failed: {e}. Falling back to local env.")

load_dotenv()
load_aws_configurations()

class Settings(BaseSettings):
    APP_NAME: str = "LeadFlowAI Secure Platform"
    DEBUG: bool = False
    BASE_URL: str = "http://localhost:8000"
    DATABASE_URL: str = Field(..., description="Database connection string")
    SECRET_KEY: str = Field(..., min_length=32)
    ENCRYPTION_KEY: str = Field(...)
    
    # --- CRITICAL FIXES ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 
    ALGORITHM: str = "HS256"  # Must be present for JWT to work!
    # ----------------------

    CLOUDFLARE_TOKEN: str | None = None
    GIT_TOKEN: str | None = None
    OPENAI_API_KEY: str = Field(default="")
    GOOGLE_API_KEY: str = Field(default="")
    MESHULAM_PAGE_CODE: str | None = None
    MESHULAM_API_KEY: str | None = None

    # Defaults to False, we will override this via ENV in Podman
    ENABLE_REAL_PHONE_PURCHASE: bool = False
    
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TELNYX_API_KEY: str | None = None
    VONAGE_API_KEY: str | None = None
    VONAGE_API_SECRET: str | None = None
    VONAGE_APP_ID: str | None = None
    VONAGE_PRIVATE_KEY_PATH: str | None = None 
    ALLOWED_HOSTS: Any = ["*"] 

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: Any) -> List[str]:
        if isinstance(v, str): return [h.strip() for h in v.split(",") if h.strip()]
        return v

    RATE_LIMIT_GLOBAL: str = "100/minute"
    RATE_LIMIT_AUTH: str = "5/hour"
    RATE_LIMIT_API: str = "60/minute"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024
    ALLOWED_AUDIO_TYPES: set = {"audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a"}

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()