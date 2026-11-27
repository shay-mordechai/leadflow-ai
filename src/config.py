import json
import logging
import os
import stat
import tempfile
import time
from pathlib import Path

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("Configuration")

CACHE_EXPIRATION_SECONDS = 3600  # 1 hour cache TTL


def _is_production_env() -> bool:
    """Return True when running in production mode."""
    env_val = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development"
    return env_val.strip().lower() == "production"


def _resolve_local_env_files() -> list[str]:
    """
    Resolve local environment files for non-production runs.
    Prioritizes .env.test when present, falling back to .env.
    """
    if _is_production_env():
        return []

    candidates: list[str] = []
    for filename in (".env.test", ".env"):
        if Path(filename).is_file():
            candidates.append(filename)
    return candidates


def _bootstrap_dotenv() -> None:
    """Load local environment variables into os.environ outside production."""
    if _is_production_env():
        return

    for env_path in _resolve_local_env_files():
        load_dotenv(dotenv_path=env_path, override=False)


_bootstrap_dotenv()


def _get_cache_dir() -> Path:
    """Return a per-user cache directory inside the system temp directory."""
    uid = os.getuid() if hasattr(os, "getuid") else "default"
    cache_dir = Path(tempfile.gettempdir()) / f"leadflow_config_{uid}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(cache_dir, stat.S_IRWXU)
    except OSError:
        pass
    return cache_dir


def _write_private_bytes(target_path: Path, data: bytes) -> None:
    """Atomically write bytes to target_path with 0600 permissions."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp_", dir=str(target_path.parent))
    tmp_path = Path(tmp_name)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(data)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, target_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _get_or_create_cache_key(key_file: Path) -> bytes:
    """
    Retrieve or generate a local Fernet key with strict 0600 permissions.
    """
    if key_file.is_file():
        try:
            os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        return key_file.read_bytes()

    key = Fernet.generate_key()
    try:
        _write_private_bytes(key_file, key)
        return key
    except FileExistsError:
        return key_file.read_bytes()


def _load_cached_secrets(cache_file: Path, key_file: Path) -> dict[str, str] | None:
    """Load and decrypt cached SSM parameters if they are fresh and valid."""
    if not cache_file.is_file() or not key_file.is_file():
        return None

    file_age = time.time() - cache_file.stat().st_mtime
    if file_age >= CACHE_EXPIRATION_SECONDS:
        return None

    key = _get_or_create_cache_key(key_file)
    fernet = Fernet(key)
    decrypted = fernet.decrypt(cache_file.read_bytes())
    payload = json.loads(decrypted.decode("utf-8"))

    if not isinstance(payload, dict) or not payload:
        return None

    logger.info("Loaded secrets from encrypted local cache (age: %ds).", int(file_age))
    return {str(k): str(v) for k, v in payload.items()}


def _save_cached_secrets(cache_file: Path, key_file: Path, secrets: dict[str, str]) -> None:
    """Encrypt and persist fetched SSM parameters using an atomic write."""
    key = _get_or_create_cache_key(key_file)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(json.dumps(secrets).encode("utf-8"))
    _write_private_bytes(cache_file, encrypted)


def _fetch_ec2_region() -> str | None:
    """Fetch the EC2 instance region via IMDSv2 with a short timeout."""
    token_resp = requests.put(
        "http://169.254.169.254/latest/api/token",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        timeout=1,
    )
    if token_resp.status_code != 200:
        return None

    imds_token = token_resp.text.strip()
    region_resp = requests.get(
        "http://169.254.169.254/latest/meta-data/placement/region",
        headers={"X-aws-ec2-metadata-token": imds_token},
        timeout=1,
    )
    if region_resp.status_code != 200:
        return None

    return region_resp.text.strip() or None


def load_aws_configurations() -> None:
    """Load configuration secrets from AWS SSM Parameter Store when enabled."""
    if os.getenv("ENABLE_AWS_SSM", "false").strip().lower() != "true":
        logger.info("Cloud-agnostic mode: skipping AWS SSM and using local environment variables.")
        return

    if _is_production_env() is False and os.getenv("APP_ENV", "").strip().lower() == "development":
        return

    cache_dir = _get_cache_dir()
    cache_file = cache_dir / "ssm_secrets_cache.enc"
    key_file = cache_dir / "ssm_cache.key"

    try:
        cached = _load_cached_secrets(cache_file, key_file)
        if cached:
            os.environ.update(cached)
            return
    except (InvalidToken, json.JSONDecodeError, OSError, ValueError) as exc:
        logger.warning("Ignoring invalid or unreadable encrypted SSM cache: %s", exc)

    try:
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or _fetch_ec2_region()
        if not region:
            logger.info("No AWS region or EC2 metadata endpoint available; skipping AWS SSM load.")
            return

        logger.info("Fetching fresh secrets from AWS SSM (region: %s)...", region)
        ssm = boto3.client("ssm", region_name=region)
        ssm_path = os.getenv("SSM_PATH_PREFIX", "/leadflow/prod/").strip()
        if not ssm_path.endswith("/"):
            ssm_path = f"{ssm_path}/"

        fetched_secrets: dict[str, str] = {}
        paginator = ssm.get_paginator("get_parameters_by_path")
        for page in paginator.paginate(Path=ssm_path, Recursive=True, WithDecryption=True):
            for param in page.get("Parameters", []):
                key = param["Name"].split("/")[-1]
                value = param["Value"]
                os.environ[key] = value
                fetched_secrets[key] = value

        if fetched_secrets:
            try:
                _save_cached_secrets(cache_file, key_file, fetched_secrets)
                logger.info(
                    "Successfully loaded and encrypted %d secrets from AWS SSM.",
                    len(fetched_secrets),
                )
            except OSError as cache_err:
                logger.warning("Could not write encrypted SSM cache file: %s", cache_err)

    except requests.exceptions.RequestException:
        logger.info("Local or non-EC2 environment detected; skipping IMDS SSM lookup.")
    except (ClientError, BotoCoreError) as exc:
        logger.error("AWS SSM client error: %s", exc)
    except Exception as exc:
        logger.warning("Unexpected error loading SSM secrets: %s", exc)


load_aws_configurations()


class Settings(BaseSettings):
    """Application runtime settings backed by environment variables and local dev/test files."""

    model_config = SettingsConfigDict(
        env_file=_resolve_local_env_files() or None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core Configuration ---
    APP_NAME: str = "LeadFlow AI"
    APP_ENV: str = Field(
        default_factory=lambda: os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development"))
    )
    SECRET_KEY: str = "temporary_dev_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    BASE_URL: str = "http://localhost:8000"
    ALLOWED_HOSTS: str = "*"

    # --- Database & Queues ---
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql+asyncpg://leadflow:leadflow_secret@db:5432/leadflow_test"
        )
    )
    READ_ONLY_DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv("READ_ONLY_DATABASE_URL", os.getenv("DATABASE_URL", ""))
    )
    REDIS_URL: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    )
    RETENTION_TTL_HOURS: int = 2160
    TRUSTED_PROXY_IPS: list[str] = []

    # --- Infrastructure ---
    S3_BUCKET_NAME: str = ""
    ENCRYPTION_KEY: str = Field(default_factory=lambda: os.getenv("ENCRYPTION_KEY", ""))
    SENTRY_DSN: str = ""

    # --- External AI APIs ---
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    BRAVE_SEARCH_API_KEY: str = ""

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

    # --- Meta / WhatsApp (Separated Messaging Bot & Admin Bot Tokens) ---
    META_ACCESS_TOKEN: str = ""
    META_ADMIN_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "my_secure_token"
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_WELCOME_TEMPLATE: str = Field(default="lead_welcome_he")
    GRAPH_API_VERSION: str = "v21.0"

    @property
    def messaging_access_token(self) -> str:
        """Return the token used by the customer-facing WhatsApp messaging bot."""
        return (self.META_ACCESS_TOKEN or "").strip()

    @property
    def admin_access_token(self) -> str:
        """
        Return META_ADMIN_ACCESS_TOKEN when configured, falling back to META_ACCESS_TOKEN.
        Used for WhatsApp Business Account and phone asset management tasks (Admin Bot).
        """
        return (self.META_ADMIN_ACCESS_TOKEN or "").strip() or (
            self.META_ACCESS_TOKEN or ""
        ).strip()

    # --- Email (SMTP) & Alerts ---
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@localhost"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp-relay.brevo.com"
    ADMIN_EMAIL: str = ""
    ALERT_WEBHOOK_URL: str = ""

    # --- Billing (Meshulam / Grow) ---
    MESHULAM_USER_ID: str = "MOCK_USER"
    MESHULAM_API_KEY: str = "MOCK_API_KEY"
    MESHULAM_PAGE_CODE: str = "MOCK_PAGE_CODE"

    # --- AI Advanced V2 Workflow Graph ---
    ENABLE_WORKFLOW_GRAPH: bool = False


def validate_config(s: Settings) -> None:
    """Validate critical runtime settings and emit warnings for missing integrations."""
    if s.APP_ENV.strip().lower() == "production":
        for disk_env in (".env", ".env.test"):
            if Path(disk_env).is_file():
                raise ValueError(
                    f"Production configuration must not load secrets from a {disk_env} file"
                )
        if s.SECRET_KEY == "temporary_dev_key" or len(s.SECRET_KEY) < 32:
            raise ValueError(
                "Production SECRET_KEY must be externally supplied and at least 32 characters"
            )

    if not (s.GOOGLE_API_KEY or s.OPENAI_API_KEY):
        logger.warning("No AI engines configured (GOOGLE_API_KEY and OPENAI_API_KEY are empty).")

    if not s.WHATSAPP_APP_SECRET:
        logger.warning(
            "WHATSAPP_APP_SECRET is empty; Meta POST signature verification will reject traffic."
        )

    if not (s.messaging_access_token and s.WHATSAPP_PHONE_ID):
        logger.warning(
            "META_ACCESS_TOKEN or WHATSAPP_PHONE_ID missing; WhatsApp messaging calls will fail."
        )

    if not s.META_ADMIN_ACCESS_TOKEN:
        logger.warning(
            "META_ADMIN_ACCESS_TOKEN is not set; falling back to META_ACCESS_TOKEN for WABA/phone management."
        )


try:
    settings = Settings()
    if settings.APP_ENV.strip().lower() == "production":
        validate_config(settings)
except Exception as exc:
    logger.critical("Configuration initialization failed: %s", exc)
    raise
