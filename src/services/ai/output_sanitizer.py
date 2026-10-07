import bleach


def sanitize_ai_output(value: str) -> str:
    """Strip HTML markup from model-generated text before storing or returning it."""
    return bleach.clean(
        value,
        tags=[],
        attributes={},
        protocols=[],
        strip=True,
        strip_comments=True,
    )
