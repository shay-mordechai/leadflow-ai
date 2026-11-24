from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import settings
from src.database.models import Lead, PlanTier, User
from src.database.session import Base, get_db
from src.main import app
from src.security.dependencies import get_current_user
from src.security.hashing import get_hash

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
        email="free-tenant@my-leads.app",
        hashed_password=get_hash("StrongPass123!"),
        name="Free Trial Owner",
        business_name="Trial Clinic",
        business_type="clinic",
        plan_tier=PlanTier.FREE,
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

    def override_get_current_user():
        return tenant_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app, base_url="https://localhost") as c:
        yield c
    app.dependency_overrides.clear()


def test_free_tier_shared_sandbox_and_single_lead_limit(
    client, db_session, tenant_user, monkeypatch
):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "TWILIO_WHATSAPP_NUMBER", "+14155238886")

    plan_res = client.get("/api/v1/billing/my-plan")
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert plan_data["plan_tier"] == "FREE"
    assert plan_data["max_leads"] == 1
    join_cmd = plan_data["sandbox_join_command"]
    assert join_cmd.startswith("start ")

    sent_messages = []

    def fake_send(to_phone: str, text: str):
        sent_messages.append((to_phone, text))

    with (
        patch("src.routers.webhooks.twilio.whatsapp_adapter.send_message", side_effect=fake_send),
        patch(
            "src.routers.webhooks.twilio.ai_engine.analyze_interaction",
            new=AsyncMock(return_value={"reply_text": "שלום! איך אפשר לעזור?"}),
        ),
    ):
        # 1. Bind Lead #1 via shared Twilio Sandbox command
        r1 = client.post(
            "/webhooks/twilio/sms",
            data={
                "From": "whatsapp:+972501111111",
                "To": "whatsapp:+14155238886",
                "Body": join_cmd,
            },
        )
        assert r1.status_code == 200

        # 2. Lead #1 chats with the bot -> allowed
        r2 = client.post(
            "/webhooks/twilio/sms",
            data={
                "From": "whatsapp:+972501111111",
                "To": "whatsapp:+14155238886",
                "Body": "מה המחיר?",
            },
        )
        assert r2.status_code == 200
        assert db_session.query(Lead).filter(Lead.user_id == tenant_user.id).count() == 1

        # 3. Lead #2 binds to same tenant on shared Sandbox and sends message -> blocked by FREE 1-lead limit
        client.post(
            "/webhooks/twilio/sms",
            data={
                "From": "whatsapp:+972502222222",
                "To": "whatsapp:+14155238886",
                "Body": join_cmd,
            },
        )
        r3 = client.post(
            "/webhooks/twilio/sms",
            data={"From": "whatsapp:+972502222222", "To": "whatsapp:+14155238886", "Body": "היי"},
        )
        assert r3.status_code == 200
        assert db_session.query(Lead).filter(Lead.user_id == tenant_user.id).count() == 1
        assert any(
            "מוגבל ללקוח 1" in msg for phone, msg in sent_messages if phone == "+972502222222"
        )


def test_coupon_partial_discount_and_zero_cost_upgrade(client, db_session, tenant_user):
    # 1. Partial discount coupon (50% off PRO 199 -> 99.50 ILS)
    disc_res = client.post("/api/v1/billing/apply-coupon", json={"coupon_code": "SAVE50"})
    assert disc_res.status_code == 200
    disc_data = disc_res.json()
    assert disc_data["activated"] is False
    assert disc_data["discount_percent"] == 50
    assert disc_data["final_price"] == 99.5

    # 2. 100% coupon reduces cost to 0 ILS and immediately upgrades account to PRO
    free_res = client.post("/api/v1/billing/apply-coupon", json={"coupon_code": "FREE100"})
    assert free_res.status_code == 200
    free_data = free_res.json()
    assert free_data["activated"] is True
    assert free_data["final_price"] == 0.0
    assert free_data["plan"] == "PRO"


def test_sync_session_rag_document_ingestion(client):
    files = {"file": ("pricing.txt", "טיפול פנים קלאסי עולה 350 שח.".encode(), "text/plain")}
    res = client.post("/api/v1/knowledge/documents", files=files)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "success"
    assert body["chunk_count"] >= 1
