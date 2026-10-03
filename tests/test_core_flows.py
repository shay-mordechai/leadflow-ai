import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

# --- IMPORTS ---
from src.main import app
from src.database.session import Base, get_db
from src.database.models import User, Lead, Message, PlanTier, LeadSource

# --- CONFIG FOR IN-MEMORY TESTING ---
# Using SQLite in memory ensures tests are fast and isolated.
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
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
def client(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    
    # Dependency Override: Replace the real DB with our testing DB
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


# =====================================================================
# 🧪 TEST CASES
# =====================================================================

def test_full_auth_flow(client):
    """
    TEST 1: Registration, Login (OTP), and Token Verification via HttpOnly Cookie.
    """
    password = "SuperSecurePassword123!"
    email = "test@leadflow.app"

    # 1. Register
    reg_res = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Test User",
        "business_name": "Test Biz",
        "business_type": "Tech"
    })
    assert reg_res.status_code == 201

    # 2. Login (Triggers OTP Email)
    with patch("src.routers.auth.send_otp_email") as mock_email:
        login_res = client.post("/api/v1/auth/login", data={"username": email, "password": password})
        assert login_res.status_code == 200
        assert mock_email.called
        
        # Extract the OTP code from the mock call arguments
        otp_code = mock_email.call_args[0][1]

    # 3. Verify OTP (Sets HttpOnly Cookie)
    verify_res = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp_code})
    assert verify_res.status_code == 200

    # Extract token from secure HttpOnly cookie stored in client.cookies
    token = client.cookies.get("access_token")
    assert token is not None

    # 4. Check Profile (Authorization via Cookie)
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email
    assert me_res.json()["plan_tier"] == "STARTER"  # Enforced default


def test_billing_coupon_upgrade(client, db_session):
    """
    TEST 2: Redeeming an Admin Coupon to bypass Meshulam payment and upgrade to PRO.
    """
    user = User(email="coupon@leadflow.app", name="Coupon User", hashed_password="X", plan_tier=PlanTier.STARTER)
    db_session.add(user)
    db_session.commit()

    from src.routers.auth import create_access_token
    token = create_access_token({"sub": str(user.id), "email": user.email})
    client.cookies.set("access_token", f"Bearer {token}")

    # Redeem VIP Coupon
    res = client.post("/api/v1/billing/redeem-coupon", json={"coupon_code": "VIP_SHAY"})
    assert res.status_code == 200
    assert res.json()["plan"] == "PRO"

    db_session.refresh(user)
    assert user.plan_tier == PlanTier.PRO


def test_webhook_lead_creation_and_idempotency(client, db_session):
    """
    TEST 3: Receiving a lead from an external webhook (Zapier/Make) and preventing duplicates.
    """
    user = User(email="webhook@leadflow.app", name="Webhook User", hashed_password="X")
    db_session.add(user)
    db_session.commit()

    payload = {
        "name": "Incoming Lead",
        "phone": "0549998888",
        "source": "FACEBOOK"
    }

    # First webhook call -> Creates Lead
    with patch("src.routers.leads.whatsapp_adapter.send_message") as mock_wa:
        mock_wa.return_value = True
        res1 = client.post(f"/api/v1/leads/webhook/{user.id}", json={**payload})
        
        assert res1.status_code == 200
        assert "lead_id" in res1.json()

    # Second webhook call with same data -> Returns "already processed"
    res2 = client.post(f"/api/v1/leads/webhook/{user.id}", json={**payload})
    assert res2.status_code == 200
    assert "already processed" in res2.json()["message"]

    leads = db_session.query(Lead).filter(Lead.user_id == user.id).all()
    assert len(leads) == 1


def test_human_takeover_and_messaging(client, db_session):
    """
    TEST 4: Disabling the bot and sending a manual message via Dashboard.
    """
    user = User(email="agent@leadflow.app", name="Agent", hashed_password="X")
    db_session.add(user)
    db_session.commit()

    lead = Lead(user_id=user.id, name="Chatty Lead", phone_number="+972501234567")
    db_session.add(lead)
    db_session.commit()

    from src.routers.auth import create_access_token
    token = create_access_token({"sub": str(user.id), "email": user.email})
    client.cookies.set("access_token", f"Bearer {token}")

    # 1. Toggle Bot Off
    toggle_res = client.patch(f"/api/v1/leads/{lead.id}/bot-status", json={"bot_active": False})
    assert toggle_res.status_code == 200
    assert toggle_res.json()["bot_active"] is False

    # 2. Send Manual Message
    with patch("src.routers.leads.whatsapp_adapter.send_message") as mock_wa:
        mock_wa.return_value = True
        msg_res = client.post(f"/api/v1/leads/{lead.id}/send-message", json={"content": "Hi, Human here!"})
        
        assert msg_res.status_code == 200
        assert mock_wa.called
        assert mock_wa.call_args[1]["text"] == "Hi, Human here!"

    messages = db_session.query(Message).filter(Message.lead_id == lead.id).all()
    assert len(messages) == 1
    assert messages[0].sender_type == "human"
    assert messages[0].content == "Hi, Human here!"
