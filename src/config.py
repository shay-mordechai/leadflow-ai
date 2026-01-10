# src/config.py

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
    Manages environment variables, security policies, and infrastructure connections.
    Utilizes Pydantic for strict validation and type enforcement.
    """

    # --- General App Settings ---
    APP_NAME: str = "LeadFlowAI Secure Platform"
    DEBUG: bool = False

    # --- Infrastructure Connections ---
    DATABASE_URL: str = Field(..., description="PostgreSQL Connection String (SQLAlchemy format)")
    REDIS_URL: str = Field(..., description="Redis Connection URL for Celery Broker and Rate Limiting")

    # --- Security Secrets (CRITICAL) ---
    # Enforcing strict length requirements to prevent brute-force attacks on signed tokens.
    SECRET_KEY: str = Field(..., min_length=32, description="Master key for signing session cookies. Must be >32 chars.")

    # Key used for Fernet symmetric encryption of Sensitive PII (Personally Identifiable Information).
    ENCRYPTION_KEY: str = Field(..., description="Base64-encoded 32-byte key for database level encryption.")

    # --- AI Vendor Keys ---
    # Defaulting to empty strings allows the app to start even if one key is missing (depending on active service).
    OPENAI_API_KEY: str = Field(default="", description="API Key for OpenAI (GPT-4/Whisper)")
    GOOGLE_API_KEY: str = Field(default="", description="API Key for Google Gemini (Flash/Pro)")

    # --- Network Security Policy ---
    # We use 'Any' type here to bypass Pydantic's default JSON parsing behavior for lists.
    # This allows reading comma-separated strings directly from the .env file.
    ALLOWED_HOSTS: Any = ["localhost", "127.0.0.1"]

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: Any) -> List[str]:
        """
        Parses the ALLOWED_HOSTS environment variable.
        Converts a comma-separated string (e.g., 'localhost,127.0.0.1') into a Python list.
        """
        if isinstance(v, str):
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

    # --- Rate Limiting Policies ---
    # Defenses against DDoS and Brute Force attacks. Format: "requests/period".
    RATE_LIMIT_Global: str = "100/minute"  # Global throttle for all IPs
    RATE_LIMIT_AUTH: str = "5/hour"        # Strict limit for login/register endpoints
    RATE_LIMIT_API: str = "60/minute"      # Standard operational limit for data endpoints

    # --- File Upload Security ---
    # Mitigates DoS via large file uploads and restricts file types to audio only.
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50 MB Cap
    ALLOWED_AUDIO_TYPES: set = {"audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a"}

    # --- Pydantic Configuration ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" # Ignores extra fields in .env file not defined here
    )

    @field_validator("SECRET_KEY")
    def validate_strong_key(cls, v):
        """
        Security check to ensure default/weak keys are not used in production.
        """
        if "default" in v.lower() or "123456" in v:
            raise ValueError("SECURITY ALERT: Weak SECRET_KEY detected. Change immediately to a secure random string.")
        return v

# Initialize Global Settings Instance
settings = Settings()
