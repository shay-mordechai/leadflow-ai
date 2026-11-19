import logging
from enum import Enum
from typing import Any, Protocol

from fastapi.concurrency import run_in_threadpool
from google.genai import types

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Defines task complexity tiers for cost-optimized model routing."""

    LOW = "low"  # Simple classification, formatting, basic FAQ -> gemini-flash-lite-latest
    STANDARD = "std"  # Active WhatsApp lead conversation -> gemini-flash-latest
    HIGH = "high"  # Complex sales negotiation -> gemini-flash-latest (with fallback)


class TenantBudgetExceededError(Exception):
    """Raised when a tenant exceeds their allocated monthly token quota."""


class GeminiClientProtocol(Protocol):
    """Protocol interface for the underlying Gemini engine."""

    async def generate(self, model: str, prompt: str, **kwargs: Any) -> str: ...


class GeminiTieredRouter:
    """
    Routes AI requests across Gemini model tiers (Flash-Lite vs. Flash)
    based on task complexity, enforces per-tenant token budgets,
    and provides automatic fallback for high availability.
    """

    MODEL_LITE = "gemini-flash-lite-latest"
    MODEL_FLASH = "gemini-flash-latest"

    def __init__(self, gemini_client: GeminiClientProtocol, redis_client: Any = None) -> None:
        self.gemini = gemini_client
        self.redis = redis_client
        # In-memory fallback counter if Redis is not active in local/test environments
        self._local_usage: dict[str, int] = {}

    def select_models(self, complexity: TaskComplexity) -> tuple[str, str]:
        """Returns (primary_model, fallback_model) based on task complexity."""
        if complexity == TaskComplexity.LOW:
            return (self.MODEL_LITE, self.MODEL_FLASH)
        # For STANDARD and HIGH complexity, use Flash as primary and Lite as fast fallback
        return (self.MODEL_FLASH, self.MODEL_LITE)

    async def verify_and_record_budget(
        self,
        tenant_id: str,
        estimated_tokens: int,
        max_monthly_tokens: int = 500_000,
    ) -> None:
        """Enforces per-tenant token limits to prevent cost spikes."""
        key = f"tenant:{tenant_id}:monthly_tokens"

        if self.redis is not None:
            current_usage = await self.redis.incrby(key, estimated_tokens)
            if current_usage > max_monthly_tokens:
                await self.redis.decrby(key, estimated_tokens)
                raise TenantBudgetExceededError(f"Tenant {tenant_id} exceeded monthly token quota.")
        else:
            current_usage = self._local_usage.get(key, 0) + estimated_tokens
            if current_usage > max_monthly_tokens:
                raise TenantBudgetExceededError(f"Tenant {tenant_id} exceeded monthly token quota.")
            self._local_usage[key] = current_usage

    async def route_and_generate(
        self,
        tenant_id: str,
        prompt: str,
        complexity: TaskComplexity = TaskComplexity.STANDARD,
        max_monthly_tokens: int = 500_000,
        response_schema: Any | None = None,
        tools: list[Any] | None = None,
        system_instruction: str | None = None,
        chat_history: list[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Validates tenant budget, selects the cost-optimal Gemini model,
        and executes with automatic failover and quota rollback on failure.
        """
        # Rough token estimation (~4 characters per token)
        estimated_tokens = max(len(prompt) // 4, 50)
        await self.verify_and_record_budget(tenant_id, estimated_tokens, max_monthly_tokens)

        primary_model, fallback_model = self.select_models(complexity)

        generation_config_args: dict[str, Any] = {
            "max_output_tokens": kwargs.pop("max_output_tokens", 512),
            "temperature": kwargs.pop("temperature", 0.2),
        }
        if response_schema is not None:
            generation_config_args["response_mime_type"] = "application/json"
            generation_config_args["response_schema"] = response_schema
        if system_instruction is not None:
            generation_config_args["system_instruction"] = system_instruction
        if tools:
            generation_config_args["tools"] = tools

        config = types.GenerateContentConfig(**generation_config_args)
        contents = chat_history if chat_history is not None else prompt

        try:
            logger.info(
                "Routing AI request",
                extra={
                    "tenant_id": tenant_id,
                    "model": primary_model,
                    "complexity": complexity.value,
                },
            )
            return await run_in_threadpool(
                self.gemini.models.generate_content,
                model=primary_model,
                contents=contents,
                config=config,
            )
        except Exception as primary_err:
            logger.warning(
                f"Primary model {primary_model} failed ({primary_err}). Failing over to {fallback_model}."
            )
            try:
                return await run_in_threadpool(
                    self.gemini.models.generate_content,
                    model=fallback_model,
                    contents=contents,
                    config=config,
                )
            except Exception as fallback_err:
                # Quota Rollback on total failure
                logger.error(f"Both models failed. Releasing reserved budget for {tenant_id}.")
                await self.release_budget(tenant_id, estimated_tokens)
                raise fallback_err

    async def release_budget(self, tenant_id: str, estimated_tokens: int) -> None:
        """Rolls back token reservation in Redis or local tracking on failure."""
        key = f"tenant:{tenant_id}:monthly_tokens"
        if self.redis is not None:
            try:
                await self.redis.decrby(key, estimated_tokens)
            except Exception as e:
                logger.warning(f"Failed to release budget in Redis: {e}")
        else:
            current = self._local_usage.get(key, 0)
            self._local_usage[key] = max(0, current - estimated_tokens)
