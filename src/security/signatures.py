import hashlib
import hmac


def verify_hmac_sha256(raw_body: bytes, secret: str, received_signature: str | None) -> bool:
    """
    Validates HMAC-SHA256 signature over raw request bytes.

    Args:
        raw_body: Exact raw byte payload from request.body().
        secret: Shared webhook secret key from environment variables.
        received_signature: Hex signature received in HTTP headers.

    Returns:
        bool: True if signature matches exactly; False otherwise.
    """
    if not received_signature or not secret:
        return False

    # Normalize signature: strip common prefixes like "sha256=" if present
    clean_signature = received_signature.strip()
    if clean_signature.startswith("sha256="):
        clean_signature = clean_signature.split("sha256=", 1)[1]

    # Compute expected HMAC digest over raw bytes
    expected_digest = hmac.new(
        key=secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256
    ).hexdigest()

    # Compare digests in constant time to eliminate timing side-channel leakage
    return hmac.compare_digest(expected_digest.lower(), clean_signature.lower())
