# app/security/ai_guardrails.py
import re

from pydantic import BaseModel, Field

# 1. Input Guardrail: Heuristic patterns for Prompt Injection & Jailbreaks
INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"(?i)system\s*prompt",
    r"(?i)you\s+are\s+now\s+(in\s+)?developer\s+mode",
    r"(?i)reveal\s+your\s+(system\s+)?(instructions|prompt)",
    r"(?i)(תתעלם|שכח)\s+(את\s+|מ)?(כל\s+)?ההוראות",
    r"(?i)(גלה|חשוף|תראה)\s+(לי\s+)?(את\s+)?(הנחיות|הוראות)\s+המערכת",
    r"(?i)הנחיות\s+המערכת",
    r"(?i)מה\s+הפרומפט\s+שלך",
    # OWASP LLM06: Cross-tenant PII & sensitive record exfiltration attempts
    r"(?i)(other|all)\s+customers.{0,30}(credit\s+card|phone|email|data|details|records)",
    r"(?i)(show|give|leak|dump|export)\s+(me\s+)?(all\s+)?(credit\s+card|passwords|api[_\s]?keys|database|other\s+users)",
    r"(?i)לקוחות\s+אחרים.{0,30}(כרטיס\s+אשראי|טלפון|אימייל|פרטים)",
]

MAX_INPUT_CHARS = 1000  # Mitigates OWASP LLM10 (Unbounded Consumption)


class SanitizedLeadInput(BaseModel):
    clean_text: str = Field(..., max_length=2000)
    is_flagged: bool = False
    risk_reason: str | None = None


def inspect_and_wrap_input(raw_user_message: str) -> SanitizedLeadInput:
    """
    Pre-LLM Guardrail: Enforces length bounds, neutralizes delimiter escapes,
    and detects prompt injection attempts before hitting the LLM API.
    """
    # Step 1: Enforce strict length bound
    truncated = raw_user_message.strip()[:MAX_INPUT_CHARS]

    # Step 2: Strip XML/delimiter tags so user cannot break out of sandboxed tags
    escaped = re.sub(r"</?untrusted_user_input>", "", truncated, flags=re.IGNORECASE)

    # Step 3: Check for common prompt injection heuristics
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, escaped):
            return SanitizedLeadInput(
                clean_text="[REDACTED_SUSPICIOUS_INPUT]",
                is_flagged=True,
                risk_reason="Potential Prompt Injection (OWASP LLM01)",
            )

    # Step 4: Structural framing using XML delimiters
    wrapped = f"<untrusted_user_input>\n{escaped}\n</untrusted_user_input>"
    return SanitizedLeadInput(clean_text=wrapped, is_flagged=False)


def validate_llm_output(llm_reply: str, forbidden_markers: list[str]) -> str:
    """
    Post-LLM Output Guardrail: Prevents system prompt leakage (OWASP LLM07)
    before the response passes to the Envoy Wasm DLP filter and WhatsApp API.
    """
    for marker in forbidden_markers:
        if marker.lower() in llm_reply.lower():
            return "אשמח לעזור לך בנוגע לשירותים שלנו. איך אוכל לחזור אליך?"
    return llm_reply
