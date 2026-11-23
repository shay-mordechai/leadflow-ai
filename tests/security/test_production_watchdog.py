# tests/security/test_production_watchdog.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.monitoring.watchdog import (
    AlertDispatcher,
    ProductionWatchdog,
    validate_webhook_url,
)


def test_validate_webhook_url_ssrf_protections():
    assert validate_webhook_url("https://hooks.slack.com/services/T00/B00/X00") is True
    assert validate_webhook_url("http://hooks.slack.com/services/T00/B00/X00") is False
    assert validate_webhook_url("https://127.0.0.1/webhook") is False
    assert validate_webhook_url("https://localhost/webhook") is False
    assert validate_webhook_url("https://169.254.169.254/latest") is False
    assert validate_webhook_url("https://10.0.0.1/webhook") is False


@pytest.mark.asyncio
async def test_alert_dispatcher_cooldown_and_pii_redaction():
    redis_mock = AsyncMock()
    redis_mock.set.return_value = True

    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        with patch("src.services.monitoring.watchdog.settings") as mock_settings:
            mock_settings.ALERT_WEBHOOK_URL = "https://webhook.site/test"

            dispatched = await AlertDispatcher.dispatch(
                alert_type="test_alert",
                title="Test Incident",
                message="User phone +972501234567 reported issue with text secret 1234.",
                severity="CRITICAL",
                redis_client=redis_mock,
            )
            assert dispatched is True
            mock_post.assert_called_once()
            call_json = mock_post.call_args[1]["json"]
            assert "+972*****" in call_json["message"]
            assert "+972501234567" not in call_json["message"]

    redis_mock.set.return_value = False
    dispatched_again = await AlertDispatcher.dispatch(
        alert_type="test_alert",
        title="Test Incident",
        message="Another alert",
        severity="CRITICAL",
        redis_client=redis_mock,
    )
    assert dispatched_again is False


@pytest.mark.asyncio
async def test_production_watchdog_llm_error_rate_and_dlq():
    redis_mock = AsyncMock()

    async def mock_get(key):
        if key == "llm:metrics:success":
            return "2"
        if key == "llm:metrics:error":
            return "8"
        if key == "llm:metrics:escalated":
            return "0"
        return None

    redis_mock.get.side_effect = mock_get
    redis_mock.llen.return_value = 2
    redis_mock.set.return_value = True

    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        with patch("src.services.monitoring.watchdog.settings") as mock_settings:
            mock_settings.ALERT_WEBHOOK_URL = "https://webhook.site/test"

            results = await ProductionWatchdog.run_checks(redis_mock)
            assert results["llm_anomaly"] is True
            assert results["dlq_anomaly"] is True
            assert results["alerts_sent"] == 2
