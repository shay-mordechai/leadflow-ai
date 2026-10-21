# tests/security/test_sec_015_twilio_signature_validation.py
import base64
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

import src.database.models  # noqa
from src.config import settings
from src.database.models import Base, PhoneNumber, User
from src.database.session import SessionLocal, engine
from temp_test_app import app  # Import the temporary test app


@pytest.fixture(autouse=True, scope="session")
def setup_db():
    import src.database.models  # noqa

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client")
def client_fixture():
    return TestClient(app)


# Helper function to generate Twilio signature
def generate_twilio_signature(url, params, auth_token):
    # Twilio orders POST parameters alphabetically by key
    sorted_params = ""
    for key in sorted(params.keys()):
        sorted_params += params[key]

    message = (url + sorted_params).encode("utf-8")
    digest = hmac.new(auth_token.encode("utf-8"), message, hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_twilio_webhook_with_valid_signature(client, mocker):
    # Seed a mock phone number and user in DB
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if not db.query(PhoneNumber).filter_by(number="+97233829709").first():
            user = User(
                email="owner@example.com",
                name="Owner",
                hashed_password="pw",
                business_name="Clinic",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            phone = PhoneNumber(number="+97233829709", is_active=True, owner_id=user.id)
            db.add(phone)
            db.commit()

    # Mock TWILIO_AUTH_TOKEN
    mocker.patch.object(settings, "TWILIO_AUTH_TOKEN", "test_auth_token")

    from unittest.mock import AsyncMock

    # Mock Twilio service dependencies to avoid external calls
    mocker.patch(
        "src.services.ai.engine.ai_engine.analyze_interaction",
        new_callable=AsyncMock,
        return_value={"is_broadcast": False},
    )
    mocker.patch(
        "src.services.ai.whisper.whisper_service.transcribe_from_url",
        new_callable=AsyncMock,
        return_value="transcribed text",
    )
    mocker.patch("src.services.communication.whatsapp.whatsapp_adapter.send_message")
    mocker.patch("src.tasks.audio_tasks.process_audio_message.delay")

    test_url = "http://testserver/webhooks/twilio/sms"
    form_data = {
        "From": "+1234567890",
        "To": "+97233829709",  # This number should exist in your mocked DB or handled by your webhook logic
        "Body": "Hello from Twilio",
        "NumMedia": "0",
    }

    # Generate a valid signature
    valid_signature = generate_twilio_signature(test_url, form_data, settings.TWILIO_AUTH_TOKEN)

    headers = {"X-Twilio-Signature": valid_signature}
    response = client.post(test_url, data=form_data, headers=headers)

    # Expect a successful response (Twilio's TwiML response is usually 200 OK)
    assert response.status_code == 200
    assert "<Response" in response.text  # Assuming a TwiML response for now


def test_twilio_webhook_with_missing_signature(client, mocker):
    # Mock TWILIO_AUTH_TOKEN
    mocker.patch.object(settings, "TWILIO_AUTH_TOKEN", "test_auth_token")

    test_url = "http://testserver/webhooks/twilio/sms"
    form_data = {
        "From": "+1234567890",
        "To": "+97233829709",
        "Body": "Hello from Twilio",
        "NumMedia": "0",
    }

    # No signature header
    response = client.post(test_url, data=form_data)

    assert response.status_code == 403
    assert response.json() == {"detail": "Twilio Signature Required"}


def test_twilio_webhook_with_invalid_signature(client, mocker):
    # Mock TWILIO_AUTH_TOKEN
    mocker.patch.object(settings, "TWILIO_AUTH_TOKEN", "test_auth_token")

    test_url = "http://testserver/webhooks/twilio/sms"
    form_data = {
        "From": "+1234567890",
        "To": "+97233829709",
        "Body": "Hello from Twilio",
        "NumMedia": "0",
    }

    # Forged signature
    forged_signature = "invalid_signature_abcd"
    headers = {"X-Twilio-Signature": forged_signature}
    response = client.post(test_url, data=form_data, headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid Twilio Signature"}


def test_twilio_webhook_with_mocked_owner_and_lead(client, mocker):
    # This test ensures the happy path of the webhook still works with validation
    mocker.patch.object(settings, "TWILIO_AUTH_TOKEN", "test_auth_token")

    # No database interaction needed for this isolated test
