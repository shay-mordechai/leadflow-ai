# src/config.py
import os
import logging
import requests
import boto3
from typing import Any, List, Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

logger = logging.getLogger("Configuration")
logging.basicConfig(level=logging.INFO)

def load_aws_configurations():
    ssm_path = "/leadflow/prod/"
    region = "eu-north-1" 
    try:
        # EC2 Metadata Check
        token_url = "http://169.254.169.254/latest/api/token"
        headers = {"X-aws-ec2-metadata-token-ttl-seconds": "1"}
        token_resp = requests.put(token_url, headers=headers, timeout=0.5)
        if token_resp.status_code == 200:
            region_url = "http://169.254.169.254/latest/meta-data/placement/region"
            headers = {"X-aws-ec2-metadata-token": token_resp.text}
            region_resp = requests.get(region_url, headers=headers, timeout=0.5)
            if region_resp.status_code == 200:
                region = region_resp.text

        # SSM Load
        ssm_client = boto3.client('ssm', region_name=region)
        paginator = ssm_client.get_paginator('get_parameters_by_path')
        page_iterator = paginator.paginate(Path=ssm_path, Recursive=True, WithDecryption=True)

        params_loaded = 0
        for page in page_iterator:
            for param in page.get('Parameters', []):
                key = param['Name'].split("/")[-1]
                os.environ[key] = param['Value']
                params_loaded += 1
        
        if params_loaded > 0: logger.info(f"✅ Loaded {params_loaded} secrets from SSM.")

    except Exception as e:
        logger.warning(f"⚠️ SSM Load Issue: {e}")

load_dotenv()
load_aws_configurations()

class Settings(BaseSettings):
    APP_NAME: str = "LeadFlowAI"
    BASE_URL: str = "https://my-leads.app"
    DATABASE_URL: str = Field(...)
    SECRET_KEY: str = Field(...)
    ENCRYPTION_KEY: str = Field(...)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 
    ALGORITHM: str = "HS256"

    # API Keys
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    
    # SignalWire (The Missing Piece!)
    SIGNALWIRE_PROJECT_ID: Optional[str] = None
    SIGNALWIRE_AUTH_TOKEN: Optional[str] = None
    SIGNALWIRE_SPACE_URL: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()