"""Redis-backed revocation for individually logged-out JWTs."""

import asyncio
import hashlib
import logging
import weakref
from datetime import UTC, datetime

import jwt  # New import
from fastapi import HTTPException, status
from jwt.exceptions import PyJWTError  # New import
from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from src.config import settings

_redis_clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Redis] = (
    weakref.WeakKeyDictionary()
)
redis_client: Redis | None = None
logger = logging.getLogger("TokenRevocation")
_development_revoked_tokens: set[str] = set()


def _get_redis() -> Redis:
    """Returns a Redis client instance bound to the running event loop or test override."""
    override = globals().get("redis_client")
    if override is not None:
        return override
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        client = _redis_clients.get(loop)
        if client is None:
            client = from_url(settings.REDIS_URL, decode_responses=True)
            _redis_clients[loop] = client
        return client
    return from_url(settings.REDIS_URL, decode_responses=True)


def _token_key(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"auth:revoked:{digest}"


def _remaining_token_lifetime(token: str) -> int:
    try:
        claims = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        expires_at = int(claims["exp"])
    except (PyJWTError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    return max(0, expires_at - int(datetime.now(UTC).timestamp()))


async def revoke_token(token: str) -> None:
    """Add a valid token digest to Redis until its expiration time."""
    ttl = _remaining_token_lifetime(token)
    if ttl <= 0:
        return
    try:
        r = _get_redis()
        await r.set(_token_key(token), "1", ex=ttl)
    except RedisError as error:
        if settings.APP_ENV != "production":
            logger.warning(
                "Redis token revocation unavailable; using process-local development blocklist (%s)",
                type(error).__name__,
            )
            _development_revoked_tokens.add(_token_key(token))
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication revocation service unavailable",
        ) from error


async def ensure_token_not_revoked(token: str) -> None:
    """Reject malformed, expired, or Redis-blocklisted tokens."""
    key = _token_key(token)
    if settings.APP_ENV != "production" and key in _development_revoked_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        r = _get_redis()
        if await r.exists(key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except RedisError as error:
        if settings.APP_ENV != "production":
            logger.warning(
                "Redis token revocation unavailable; checking process-local development blocklist (%s)",
                type(error).__name__,
            )
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication revocation service unavailable",
        ) from error
