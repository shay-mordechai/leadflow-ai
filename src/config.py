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
    """
    Attempts to load configuration and secrets from AWS SSM Parameter Store.
    
    Mechanism:
    1. Tries to connect to AWS IMDSv2 to get a session token.
    2. If successful, identifies the current AWS Region.
    3. Connects to SSM Parameter Store in that region.
    4. Fetches all parameters under '/leadflow/prod/' (recursive) with decryption.
    5. Injects them into os.environ for Pydantic to pick up.
    
    Fallback:
    If not running on EC2 or if AWS calls fail, it defaults gracefully to local environment variables.
    """
    try:
        # Step 1: Request IMDSv2 Token (Validity: 6 hours)
        token_url = "http://169.254.169.254/latest/api/token"
        headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        
        # Fast timeout to fail quickly if running locally
        token_response = requests.put(token_url, headers=headers, timeout=1)
        
        if token_response.status_code != 200:
            return # Not on AWS EC2
            
        token = token_response.text

        # Step 2: Get Current Region using the Token
        region_url = "http://169.254.169.254/latest/meta-data/placement/region"
        region_headers = {"X-aws-ec2-metadata-token": token}
        region_response = requests.get(region_url, headers=region_headers, timeout=1)
        region = region_response.text

        logger.info(f"☁️ Detected AWS Environment (Region: {region}). Initializing SSM...")

        # Step 3: Initialize Boto3 SSM Client
        ssm = boto3.client('ssm', region_name=region)
        
        # Configuration Path in SSM (Namespace)
        ssm_path = "/leadflow/prod/" 

        # Step 4: Fetch Parameters (Handling Pagination)
        paginator = ssm.get_paginator('get_parameters_by_path')
        page_iterator = paginator.paginate(
            Path=ssm_path,
            Recursive=True,
            WithDecryption=True
        )

        params_loaded = 0
        for page in page_iterator:
            for param in page.get('Parameters', []):
                # Logic: /leadflow/prod/DB_PASSWORD -> DB_PASSWORD
                key = param['Name'].split("/")[-1]
                value = param['Value']
                
                # Injected into environment for Pydantic Settings to pick up
                os.environ[key] = value
                params_loaded += 1
        
        logger.info(f"🔐 Successfully loaded {params_loaded} secrets from AWS SSM.")

    except requests.exceptions.RequestException:
        # Likely local environment or metadata service unreachable
        pass
    except Exception as e:
        logger.warning(f"⚠️ AWS SSM Load Failed: {e}. Falling back to local env.")

# 1. Load Local .env (Development/Local)
load_dotenv()

# 2. Load AWS Secrets (Production Override)
load_aws_configurations()

class Settings(BaseSettings):
    """
    Application Configuration Class.
    Integrated with Pydantic Settings for type safety and validation.
    Priority: AWS SSM (if on EC2) > Local .env > Defaults.
    """

    # --- General App Settings ---
    APP_NAME: str = "LeadFlowAI Secure Platform"
    DEBUG: bool = False
    BASE_URL: str = "http://localhost:8000"

    # --- Infrastructure Connections ---
    DATABASE_URL: str = Field(..., description="Database connection string (SQLite/Postgres)")

    # --- Security Secrets ---
    SECRET_KEY: str = Field(..., min_length=32, description="JWT Signing Key")
    ENCRYPTION_KEY: str = Field(..., description="Fernet Key for PII Encryption")
    
    # --- Third Party Integration Tokens ---
    CLOUDFLARE_TOKEN: str | None = Field(default=None, description="Cloudflare API/Tunnel Token")
    GIT_TOKEN: str | None = Field(default=None, description="GitHub Token for CI/CD operations")

    # --- AI Vendor Keys ---
    OPENAI_API_KEY: str = Field(default="")
    GOOGLE_API_KEY: str = Field(default="")

    # --- Payment Keys (Meshulam) ---
    MESHULAM_PAGE_CODE: str | None = None
    MESHULAM_API_KEY: str | None = None

    # --- Phone Providers Credentials ---
    ENABLE_REAL_PHONE_PURCHASE: bool = False
    
    # Twilio
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None

    # Telnyx
    TELNYX_API_KEY: str | None = None

    # Vonage (Nexmo)
    VONAGE_API_KEY: str | None = None
    VONAGE_API_SECRET: str | None = None
    VONAGE_APP_ID: str | None = None
    VONAGE_PRIVATE_KEY_PATH: str | None = None 

    # --- Network Security Policy ---
    ALLOWED_HOSTS: Any = ["*"] 

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

    # --- Rate Limiting Policies ---
    RATE_LIMIT_GLOBAL: str = "100/minute"
    RATE_LIMIT_AUTH: str = "5/hour"
    RATE_LIMIT_API: str = "60/minute"

    # --- File Upload Security ---
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024
    ALLOWED_AUDIO_TYPES: set = {"audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a"}

    # Pydantic Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Global settings instance
settings = Settings()