import os
from typing import Any, List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application Configuration Class.
    Fully integrated with Pydantic for production safety.
    """

    # --- General App Settings ---
    APP_NAME: str = "LeadFlowAI Secure Platform"
    DEBUG: bool = False

    # --- Infrastructure Connections ---
    DATABASE_URL: str = Field(..., description="PostgreSQL Connection String")
    REDIS_URL: str = Field(..., description="Redis Connection URL")

    # --- Security Secrets ---
    SECRET_KEY: str = Field(..., min_length=32)
    ENCRYPTION_KEY: str = Field(...)

    # --- AI Vendor Keys ---
    OPENAI_API_KEY: str = Field(default="")
    GOOGLE_API_KEY: str = Field(default="")

    # --- Network Security Policy ---
    # Professional comment: Domains authorized to bypass the TrustedHostMiddleware
    ALLOWED_HOSTS: Any = ["*"] #["my-leads.app", "www.my-leads.app", "localhost", "127.0.0.1"]

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

    # --- Rate Limiting Policies (REQUIRED BY MAIN.PY) ---
    # Professional comment: Re-adding attributes to fix the AttributeError in main.py
    RATE_LIMIT_Global: str = "100/minute"
    RATE_LIMIT_AUTH: str = "5/hour"
    RATE_LIMIT_API: str = "60/minute"

    # --- File Upload Security ---
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024
    ALLOWED_AUDIO_TYPES: set = {"audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a"}

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Professional comment: Global settings instance for use across the application
settings = Settings()
