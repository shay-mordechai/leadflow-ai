# src/services/ai/tracing.py
import logging
import uuid

from src.security.pii import mask_body

logger = logging.getLogger("AITracing")


def record_ai_turn_trace(
    tenant_id: str,
    lead_id: str,
    model_used: str,
    complexity_tier: str,
    latency_ms: float,
    input_tokens: int,
    output_tokens: int,
    cache_hit: bool,
    abstained: bool,
    needs_human: bool,
) -> str:
    """
    Records a PII-safe structured JSON trace for an AI turn, ensuring phone numbers,
    emails, and message bodies are scrubbed or masked.
    """
    trace_id = str(uuid.uuid4())
    log_payload = {
        "trace_id": trace_id,
        "tenant_id": mask_body(tenant_id, max_len=6),
        "lead_id": mask_body(lead_id, max_len=6),
        "model_used": model_used,
        "complexity_tier": complexity_tier,
        "latency_ms": round(latency_ms, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_hit": cache_hit,
        "abstained": abstained,
        "needs_human": needs_human,
    }
    logger.info("🤖 AI Turn Trace Recorded", extra=log_payload)
    return trace_id
