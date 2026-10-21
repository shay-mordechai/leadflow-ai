from unittest.mock import AsyncMock

import pytest

from src.services.llm_router import (
    GeminiTieredRouter,
    TaskComplexity,
    TenantBudgetExceededError,
)


class DummyGeminiClient:
    """Mock implementation of the Gemini client for deterministic unit testing."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.should_fail_model: str | None = None

    async def generate(self, model: str, prompt: str, **kwargs) -> str:
        self.calls.append((model, prompt))
        if self.should_fail_model == model:
            raise RuntimeError(f"Simulated upstream API timeout for {model}")
        return f"response_from_{model}"


@pytest.mark.asyncio
async def test_tiered_model_routing_by_complexity() -> None:
    """Verifies that low-complexity tasks route to Flash-Lite and standard tasks route to Flash."""
    client = DummyGeminiClient()
    router = GeminiTieredRouter(gemini_client=client)

    res_low = await router.route_and_generate(
        tenant_id="tenant_1",
        prompt="Classify this short greeting",
        complexity=TaskComplexity.LOW,
    )
    assert res_low == f"response_from_{GeminiTieredRouter.MODEL_LITE}"
    assert client.calls[-1][0] == GeminiTieredRouter.MODEL_LITE

    res_std = await router.route_and_generate(
        tenant_id="tenant_1",
        prompt="Handle customer price objection in WhatsApp",
        complexity=TaskComplexity.STANDARD,
    )
    assert res_std == f"response_from_{GeminiTieredRouter.MODEL_FLASH}"
    assert client.calls[-1][0] == GeminiTieredRouter.MODEL_FLASH


@pytest.mark.asyncio
async def test_tenant_budget_enforcement_blocks_excessive_usage() -> None:
    """Ensures a tenant cannot exceed their allocated monthly token quota (Denial of Wallet protection)."""
    client = DummyGeminiClient()
    router = GeminiTieredRouter(gemini_client=client)

    await router.route_and_generate(
        tenant_id="tenant_abuse",
        prompt="Short prompt",
        max_monthly_tokens=60,
    )

    with pytest.raises(TenantBudgetExceededError):
        await router.route_and_generate(
            tenant_id="tenant_abuse",
            prompt="Second prompt exceeding quota",
            max_monthly_tokens=60,
        )

    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_cross_tenant_budget_isolation() -> None:
    """Verifies that one tenant exhausting their quota does not impact other tenants."""
    client = DummyGeminiClient()
    router = GeminiTieredRouter(gemini_client=client)

    with pytest.raises(TenantBudgetExceededError):
        await router.route_and_generate(
            tenant_id="tenant_a",
            prompt="A" * 400,
            max_monthly_tokens=50,
        )

    response = await router.route_and_generate(
        tenant_id="tenant_b",
        prompt="Hello from tenant B",
        max_monthly_tokens=50,
    )
    assert response == f"response_from_{GeminiTieredRouter.MODEL_FLASH}"


@pytest.mark.asyncio
async def test_redis_atomic_budget_rollback_on_exceed() -> None:
    """Validates that Redis counters are rolled back via decrby when a request exceeds the quota."""
    client = DummyGeminiClient()
    mock_redis = AsyncMock()
    mock_redis.incrby.return_value = 550_000

    router = GeminiTieredRouter(gemini_client=client, redis_client=mock_redis)

    with pytest.raises(TenantBudgetExceededError):
        await router.route_and_generate(
            tenant_id="tenant_redis",
            prompt="Test prompt",
            max_monthly_tokens=500_000,
        )

    mock_redis.incrby.assert_awaited_once_with("tenant:tenant_redis:monthly_tokens", 50)
    mock_redis.decrby.assert_awaited_once_with("tenant:tenant_redis:monthly_tokens", 50)
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_automatic_model_failover_on_upstream_error() -> None:
    """Ensures high availability by failing over to the backup model when the primary model fails."""
    client = DummyGeminiClient()
    client.should_fail_model = GeminiTieredRouter.MODEL_FLASH
    router = GeminiTieredRouter(gemini_client=client)

    response = await router.route_and_generate(
        tenant_id="tenant_ha",
        prompt="Important lead message",
        complexity=TaskComplexity.HIGH,
    )

    assert response == f"response_from_{GeminiTieredRouter.MODEL_LITE}"
    assert len(client.calls) == 2
    assert client.calls[0][0] == GeminiTieredRouter.MODEL_FLASH
    assert client.calls[1][0] == GeminiTieredRouter.MODEL_LITE
