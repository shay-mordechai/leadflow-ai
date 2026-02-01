import os
import logging
import requests
import boto3
from typing import Any, List, Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

# --- Logging Setup ---
logger = logging.getLogger("Configuration")
logging.basicConfig(level=logging.INFO)

def load_aws_configurations():
    """
    Loads secrets from AWS SSM Parameter Store.
    """
    ssm_path = "/leadflow/prod/"
    # Default Region
    region = "eu-north-1" 

    # 1. Try to get Region from EC2 Metadata (Production)
    try:
        token_url = "http://169.254.169.254/latest/api/token"
        headers = {"X-aws-ec2-metadata-token-ttl-seconds": "1"}
        token_response = requests.put(token_url, headers=headers, timeout=0.5)
        
        if token_response.status_code == 200:
            token = token_response.text
            region_url = "http://169.254.169.254/latest/meta-data/placement/region"
            region_headers = {"X-aws-ec2-metadata-token": token}
            region_resp = requests.get(region_url, headers=region_headers, timeout=0.5)
            if region_resp.status_code == 200:
                region = region_resp.text
                logger.info(f"☁️ Running on AWS EC2 (Region: {region})")
    except (requests.exceptions.RequestException, requests.exceptions.Timeout):
        logger.info(f"💻 Running Locally. Defaulting to Region: {region}")

    # 2. Connect to SSM
    try:
        ssm_client = boto3.client('ssm', region_name=region)
        paginator = ssm_client.get_paginator('get_parameters_by_path')
        page_iterator = paginator.paginate(Path=ssm_path, Recursive=True, WithDecryption=True)

        params_loaded = 0
        for page in page_iterator:
            for param in page.get('Parameters', []):
                key = param['Name'].split("/")[-1]
                value = param['Value']
                os.environ[key] = value
                params_loaded += 1
        
        if params_loaded > 0:
            logger.info(f"✅ Successfully loaded {params_loaded} secrets from SSM.")
    except (NoCredentialsError, PartialCredentialsError):
        logger.warning("⚠️ No AWS Credentials found! Cannot load from SSM.")
    except Exception as e:
        logger.warning(f"⚠️ SSM Load Failed: {e}")

# Load .env first, then SSM overrides
load_dotenv()
load_aws_configurations()

class Settings(BaseSettings):
    APP_NAME: str = "LeadFlowAI Secure Platform"
    
    # --- 🔴 THIS WAS MISSING ---
    DEBUG: bool = False
    # ---------------------------

    BASE_URL: str = "https://my-leads.app"

    DATABASE_URL: str = Field(..., description="Database connection string")
    SECRET_KEY: str = Field(..., min_length=32)
    ENCRYPTION_KEY: str = Field(...)
    
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 
    ALGORITHM: str = "HS256"

    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    
    # Providers
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None

    # SignalWire Config
    SIGNALWIRE_PROJECT_ID: Optional[str] = None
    SIGNALWIRE_AUTH_TOKEN: Optional[str] = None
    SIGNALWIRE_SPACE_URL: Optional[str] = None

    VONAGE_API_KEY: Optional[str] = None
    VONAGE_API_SECRET: Optional[str] = None
    
    # Networking
    ALLOWED_HOSTS: Any = ["*"] 
    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: Any) -> List[str]:
        if isinstance(v, str): return [h.strip() for h in v.split(",") if h.strip()]
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
