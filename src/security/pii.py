# src/security/pii.py
import hashlib


def mask_phone(phone: str | None) -> str:
    """Mask phone number for logs and diagnostics to protect user PII (e.g., +972*****709)."""
    if not phone:
        return "[REDACTED]"
    cleaned = phone.strip()
    if len(cleaned) <= 6:
        return "***" + cleaned[-3:] if len(cleaned) >= 3 else "***"
    return f"{cleaned[:4]}*****{cleaned[-3:]}"


def mask_body(body: str | None, max_len: int = 10) -> str:
    """Mask message body content for logs to prevent plain-text PII disclosure."""
    if not body:
        return "[EMPTY]"
    clean_body = body.strip()
    if len(clean_body) <= max_len:
        return f"[REDACTED len={len(clean_body)}]"
    return f"[REDACTED len={len(clean_body)} preview={clean_body[:4]}...{clean_body[-3:]}]"


def hash_identifier(identifier: str | None) -> str:
    """Hash sensitive identifiers for secure idempotency keys or audit logging."""
    if not identifier:
        return "nil"
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    print("Phone masked:", mask_phone("+972501234567"))
    print("Body masked:", mask_body("Hello world"))
    print("Hashed ID:", hash_identifier("+972501234567"))
