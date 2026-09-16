import json
import logging
import os
import asyncio
from typing import Dict, Any

logger = logging.getLogger("ProfileLoader")

FALLBACK_PROFILE: Dict[str, Any] = {
    "business_name": "Customer Support",
    "business_type": "General Service",
    "tone": "polite, helpful and concise",
    "currency": "ILS",
    "services": [],
    "pricing": {},
    "faqs": [],
    "qualification_funnel": {
        "ask_name": True,
        "ask_service": True,
        "ask_budget": True,
        "ask_availability": True
    }
}

def _read_profile_sync(file_path: str) -> Dict[str, Any]:
    """Synchronous file read executed inside a worker thread."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

async def load_tenant_profile(file_path: str | None) -> Dict[str, Any]:
    """
    Asynchronously loads a tenant profile JSON file from disk.
    Returns FALLBACK_PROFILE if file is missing, empty, or corrupted.
    """
    if not file_path:
        logger.debug("No business profile path set. Using fallback profile.")
        return FALLBACK_PROFILE

    normalized_path = os.path.abspath(file_path)

    if not os.path.exists(normalized_path):
        logger.warning(f"Profile file not found at: {normalized_path}. Using fallback.")
        return FALLBACK_PROFILE

    try:
        profile_data = await asyncio.to_thread(_read_profile_sync, normalized_path)
        if isinstance(profile_data, dict):
            return profile_data
        logger.warning(f"Invalid JSON root in {normalized_path}, expected dictionary.")
        return FALLBACK_PROFILE
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON profile at {normalized_path}: {e}")
        return FALLBACK_PROFILE
    except Exception as e:
        logger.error(f"Unexpected error loading profile at {normalized_path}: {e}")
        return FALLBACK_PROFILE
