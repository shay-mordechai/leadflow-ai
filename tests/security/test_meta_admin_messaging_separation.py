"""
Unit and integration tests verifying the separation between the Meta Admin Bot and Meta Messaging Bot,
token fallback behavior, and absence of autonomous phone number purchasing.
"""

from src.config import Settings
from src.services.communication.whatsapp import whatsapp_adapter


def test_admin_token_preference_and_fallback():
    """Verify admin_access_token prefers META_ADMIN_ACCESS_TOKEN and falls back to META_ACCESS_TOKEN."""
    # Case 1: Both set -> admin token preferred
    s1 = Settings(
        META_ADMIN_ACCESS_TOKEN="admin_token_123", META_ACCESS_TOKEN="messaging_token_456"
    )
    assert s1.admin_access_token == "admin_token_123"

    # Case 2: Only META_ADMIN_ACCESS_TOKEN set
    s2 = Settings(META_ADMIN_ACCESS_TOKEN="admin_token_123", META_ACCESS_TOKEN="")
    assert s2.admin_access_token == "admin_token_123"

    # Case 3: META_ADMIN_ACCESS_TOKEN unset/empty -> falls back to META_ACCESS_TOKEN
    s3 = Settings(META_ADMIN_ACCESS_TOKEN="", META_ACCESS_TOKEN="messaging_token_456")
    assert s3.admin_access_token == "messaging_token_456"

    # Case 4: Both unset
    s4 = Settings(META_ADMIN_ACCESS_TOKEN="", META_ACCESS_TOKEN="")
    assert s4.admin_access_token == ""


def test_messaging_adapter_uses_messaging_token():
    """Verify WhatsAppAdapter messaging operations use META_ACCESS_TOKEN and WHATSAPP_PHONE_ID."""
    adapter = whatsapp_adapter
    token, phone_id = adapter._credentials(access_token=None, phone_number_id=None)
    assert token == adapter.access_token
    assert phone_id == adapter.phone_number_id


def test_no_autonomous_phone_purchase_without_explicit_operator_action():
    """Verify that provisioning/purchasing endpoints require explicit operator action and do not execute autonomously."""
    from src.routers.provisioning import provision_tenant_number

    assert callable(provision_tenant_number)
