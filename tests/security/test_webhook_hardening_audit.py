# tests/security/test_webhook_hardening_audit.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routers.webhooks import meshulam, twilio, whatsapp
from src.security.pii import hash_identifier, mask_body, mask_phone

app = FastAPI()
app.include_router(twilio.router, prefix="/webhooks/twilio")
app.include_router(whatsapp.router, prefix="/webhooks/whatsapp")
app.include_router(meshulam.router, prefix="/webhooks/meshulam")


@pytest.fixture(name="client")
def client_fixture():
    return TestClient(app)


def test_pii_masking_utilities():
    """Verify that phone numbers and message bodies are properly masked for logs."""
    phone = "+972501234567"
    masked_p = mask_phone(phone)
    assert masked_p == "+972*****567"
    assert "01234" not in masked_p

    short_phone = "+1234"
    assert mask_phone(short_phone) == "***234"
    assert mask_phone(None) == "[REDACTED]"

    body = "Hello this is a very sensitive message containing confidential info."
    masked_b = mask_body(body, max_len=10)
    assert "confidential" not in masked_b
    assert "REDACTED" in masked_b

    assert mask_body(None) == "[EMPTY]"

    h = hash_identifier("+972501234567")
    assert len(h) == 16


def test_twilio_missing_signature_returns_403(client, mocker):
    """Ensure missing Twilio signature returns 403 Forbidden."""
    mocker.patch.object(twilio.settings, "TWILIO_AUTH_TOKEN", "secret-token")
    response = client.post(
        "/webhooks/twilio/sms", data={"From": "+972501234567", "To": "+97233829709", "Body": "test"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Twilio Signature Required"}


def test_whatsapp_missing_signature_returns_403(client, mocker):
    """Ensure missing WhatsApp signature returns 403 Forbidden in production or when configured."""
    mocker.patch.object(whatsapp.settings, "WHATSAPP_APP_SECRET", "app-secret")
    mocker.patch.object(whatsapp, "_is_production", return_value=True)
    response = client.post("/webhooks/whatsapp", json={"object": "whatsapp_business_account"})
    assert response.status_code == 403
    assert response.json() == {"detail": "Signature missing"}


def test_meshulam_invalid_signature_returns_403(client, mocker):
    """Ensure invalid Meshulam signature returns 403 Forbidden."""
    mocker.patch.object(meshulam.settings, "MESHULAM_API_KEY", "real-api-key")
    response = client.post(
        "/webhooks/meshulam/notify",
        data={"transactionId": "123", "sum": "100", "status": "1", "signature": "bad_sig"},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid Meshulam Signature"}
