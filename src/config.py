import os
from typing import Any, List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# Load environment variables
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
    
    # זה ה-URL הקריטי ל-Webhooks
    BASE_URL: str = "http://localhost:8000"

    # --- Infrastructure Connections ---
    DATABASE_URL: str = Field(..., description="PostgreSQL Connection String")

    # --- Security Secrets ---
    SECRET_KEY: str = Field(..., min_length=32, description="JWT Signing Key")
    ENCRYPTION_KEY: str = Field(..., description="Fernet Key for PII Encryption")

    # --- AI Vendor Keys ---
    OPENAI_API_KEY: str = Field(default="")
    GOOGLE_API_KEY: str = Field(default="")

    # --- Payment Keys (Meshulam) ---
    MESHULAM_PAGE_CODE: str | None = None
    MESHULAM_API_KEY: str | None = None

    # --- Phone Providers Credentials (NEW) ---
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
    RATE_LIMIT_Global: str = "100/minute"
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