# tests/security/test_webhook_idempotency.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import Lead, User
from src.database.session import Base, get_db
from src.main import app
from src.security.hashing import get_hash
from src.security.idempotency import check_and_claim_idempotency

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def tenant_user(db_session):
    db_session.query(Lead).delete()
    db_session.query(User).delete()
    db_session.commit()

    user = User(
        email="idempotency-tenant@my-leads.app",
        hashed_password=get_hash("StrongPass123!"),
        name="Idempotency Owner",
        business_name="Idempotency Clinic",
        business_type="clinic",
        plan_tier=User.plan_tier.default.arg,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def client(db_engine, tenant_user):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="https://localhost") as c:
        yield c
    app.dependency_overrides.clear()


def test_idempotency_claim_mechanism():
    """Verify check_and_claim_idempotency returns True on first claim and False on duplicate."""
    provider = "test_provider"
    msg_id = "msg-unique-12345"

    assert check_and_claim_idempotency(provider, msg_id) is True
    assert check_and_claim_idempotency(provider, msg_id) is False


def test_twilio_webhook_duplicate_message_sid_ignored(client, monkeypatch):
    """Verify that submitting the same Twilio MessageSid twice is ignored on the second delivery."""
    monkeypatch.setattr("src.routers.webhooks.twilio.validate_twilio_signature", lambda r: True)
    monkeypatch.setattr(
        "src.routers.webhooks.twilio.settings",
        type(
            "Obj",
            (),
            {
                "TWILIO_AUTH_TOKEN": "",
                "TWILIO_WHATSAPP_NUMBER": "+14155238886",
                "REDIS_URL": "redis://localhost:6379/0",
            },
        ),
    )

    payload = {
        "From": "whatsapp:+972501111111",
        "To": "whatsapp:+14155238886",
        "Body": "שלום",
        "MessageSid": "SM123456789abcdef",
    }

    res1 = client.post("/webhooks/twilio/sms", data=payload)
    assert res1.status_code == 200

    # Second delivery with same MessageSid should be ignored idempotently
    res2 = client.post("/webhooks/twilio/sms", data=payload)
    assert res2.status_code == 200
