import os
from typing import Any, List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# Load environment variables from .env file immediately
load_dotenv()

class Settings(BaseSettings):
    """
    Application Configuration Class.
    Fully integrated with Pydantic for production safety.
    Validates environment variables on startup.
    """

    # --- General App Settings ---
    APP_NAME: str = "LeadFlowAI Secure Platform"
    DEBUG: bool = False

    # --- Infrastructure Connections ---
    DATABASE_URL: str = Field(..., description="PostgreSQL Connection String")
    # REDIS_URL: str = Field(..., description="Redis Connection URL") # Reserved for future scaling

    # --- Security Secrets ---
    # Critical keys for signing tokens and encrypting DB data.
    SECRET_KEY: str = Field(..., min_length=32, description="JWT Signing Key")
    ENCRYPTION_KEY: str = Field(..., description="Fernet Key for PII Encryption")

    # --- AI Vendor Keys ---
    # Defaults to empty string to allow app startup in dev mode without keys.
    OPENAI_API_KEY: str = Field(default="")
    GOOGLE_API_KEY: str = Field(default="")

    # --- Network Security Policy ---
    # Domains authorized to bypass TrustedHostMiddleware.
    # In production, this should be restricted to your specific domain.
    ALLOWED_HOSTS: Any = ["*"] 

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: Any) -> List[str]:
        """Parses comma-separated string into a list of hosts."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

    # --- Rate Limiting Policies ---
    # These constants are consumed by SlowAPI in main.py to prevent abuse.
    RATE_LIMIT_Global: str = "100/minute"
    RATE_LIMIT_AUTH: str = "5/hour"
    RATE_LIMIT_API: str = "60/minute"

    # --- File Upload Security ---
    # Limits and validation for incoming media files (WhatsApp Webhooks).
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB Limit
    ALLOWED_AUDIO_TYPES: set = {"audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a"}

    # Pydantic Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra env vars not defined here
    )

# Global settings instance to be imported across the application
settings = Settings()