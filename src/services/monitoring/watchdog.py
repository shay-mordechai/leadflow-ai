# src/services/monitoring/watchdog.py
import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

import requests

from src.config import settings

logger = logging.getLogger("ProductionWatchdog")


def validate_webhook_url(url: str) -> bool:
    """Validate webhook URL against SSRF (HTTPS only, reject private/loopback/internal IPs)."""
    if not url:
        return True
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        hostname = parsed.hostname
        if not hostname:
            return False

        if hostname in ("localhost", "127.0.0.1", "::1"):
            return False

        try:
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False
        except Exception:
            pass

        return True
    except Exception:
        return False


class AlertDispatcher:
    @staticmethod
    async def dispatch(
        alert_type: str,
        title: str,
        message: str,
        severity: str = "CRITICAL",
        redis_client: Any = None,
    ) -> bool:
        """Dispatch alert with 30-minute Redis SET NX cooldown deduplication and PII sanitization."""
        safe_message = message.replace("+972", "+972*****").replace("@", "[AT]")

        cooldown_key = f"alert:cooldown:{alert_type}"
        if redis_client is not None:
            try:
                acquired = await redis_client.set(cooldown_key, "1", nx=True, ex=1800)
                if not acquired:
                    logger.info(f"Alert {alert_type} suppressed due to 30-minute cooldown.")
                    return False
            except Exception as e:
                logger.warning(f"Failed to check alert cooldown in Redis: {e}")

        webhook_url = getattr(settings, "ALERT_WEBHOOK_URL", "")
        if webhook_url:
            if not validate_webhook_url(webhook_url):
                logger.error(
                    f"Rejected insecure or internal ALERT_WEBHOOK_URL (SSRF protection): {webhook_url}"
                )
                return False
            try:
                payload = {
                    "severity": severity,
                    "title": title,
                    "message": safe_message,
                    "service": "leadflow-ai",
                }
                resp = requests.post(webhook_url, json=payload, timeout=5)
                if resp.status_code >= 400:
                    logger.error(f"Failed to dispatch alert webhook: HTTP {resp.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Exception dispatching alert webhook: {e}")
                return False

        logger.critical(f"[{severity.upper()} ALERT] {title}: {safe_message}")
        return True


class ProductionWatchdog:
    @staticmethod
    async def run_checks(redis_client: Any = None) -> dict[str, Any]:
        """Run all production monitoring checks and dispatch alerts on anomalies."""
        results = {"llm_anomaly": False, "dlq_anomaly": False, "alerts_sent": 0}

        if redis_client is not None:
            try:
                success = int(await redis_client.get("llm:metrics:success") or 0)
                error = int(await redis_client.get("llm:metrics:error") or 0)
                escalated = int(await redis_client.get("llm:metrics:escalated") or 0)
                total = success + error + escalated

                if total >= 5:
                    error_rate = error / total
                    if error_rate > 0.10:
                        results["llm_anomaly"] = True
                        await AlertDispatcher.dispatch(
                            alert_type="llm_error_rate_spike",
                            title="LLM Error Rate Spike Detected",
                            message=f"Error rate is {error_rate * 100:.1f}% ({error}/{total} calls failed in rolling window).",
                            severity="CRITICAL",
                            redis_client=redis_client,
                        )
                        results["alerts_sent"] += 1
            except Exception as e:
                logger.warning(f"Error checking LLM metrics in Redis: {e}")

        if redis_client is not None:
            try:
                dlq_size = int(await redis_client.llen("celery-dlq") or 0)
                if dlq_size > 0:
                    results["dlq_anomaly"] = True
                    await AlertDispatcher.dispatch(
                        alert_type="dlq_growth",
                        title="Celery DLQ Non-Empty",
                        message=f"Dead Letter Queue has {dlq_size} failed messages requiring operator review.",
                        severity="WARNING",
                        redis_client=redis_client,
                    )
                    results["alerts_sent"] += 1
            except Exception as e:
                logger.warning(f"Error checking Celery DLQ size in Redis: {e}")

        return results
