"""Redis-backed revocation for individually logged-out JWTs."""

import hashlib
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt
from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from src.config import settings

redis_client: Redis = from_url(settings.REDIS_URL, decode_responses=True)
logger = logging.getLogger("TokenRevocation")
_development_revoked_tokens: set[str] = set()


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
    except (JWTError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    return max(0, expires_at - int(datetime.now(timezone.utc).timestamp()))


async def revoke_token(token: str) -> None:
    """Add a valid token digest to Redis until its expiration time."""
    ttl = _remaining_token_lifetime(token)
    if ttl <= 0:
        return
    try:
        await redis_client.set(_token_key(token), "1", ex=ttl)
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
        if await redis_client.exists(key):
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
