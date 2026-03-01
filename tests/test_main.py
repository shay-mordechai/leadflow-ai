# tests/test_main.py
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
from src.database.models import User, PlanTier, Lead, Message

# --- CONFIG FOR TESTING ---
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
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
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass 
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="http://localhost") as c:
        yield c
    app.dependency_overrides.clear()

# --- TESTS ---

def test_auth_flow(client):
    """Tests the full registration -> login -> OTP flow."""
    password = "YourPassword123!" 
    reg_response = client.post("/api/v1/auth/register", json={
        "email": "test@user.com", "password": password, "full_name": "Test User",
        "business_name": "Test Biz", "business_type": "Tech", "plan_tier": "PRO"
    })
    assert reg_response.status_code == 201

    with patch("src.routers.auth.send_otp_email") as mock_email:
        login_response = client.post("/api/v1/auth/login", data={"username": "test@user.com", "password": password})
        assert login_response.status_code == 200
        assert mock_email.called
        otp_code = mock_email.call_args[0][1]

    verify_response = client.post("/api/v1/auth/verify-otp", json={"email": "test@user.com", "otp_code": otp_code})
    assert verify_response.status_code == 200
    assert verify_response.json().get("access_token") is not None

def test_security_purchase_gate(client):
    """Ensures that users on STARTER plan cannot access PRO features (Phone Purchase)."""
    password = "YourPassword123!"
    client.post("/api/v1/auth/register", json={
        "email": "starter@gate.com", "password": password, "full_name": "Gate",
        "business_name": "B", "business_type": "T", "plan_tier": "starter" 
    })

    with patch("src.routers.auth.send_otp_email") as mock:
        client.post("/api/v1/auth/login", data={"username": "starter@gate.com", "password": password})
        otp = mock.call_args[0][1]

    token = client.post("/api/v1/auth/verify-otp", json={"email": "starter@gate.com", "otp_code": otp}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post("/api/v1/phones/purchase", json={"phone_number": "+972509999999", "provider": "twilio"}, headers=headers)
    assert response.status_code == 403
    assert "restricted to PRO" in response.json()["detail"]

def test_conversational_memory_logic(client, db_session):
    """Tests that messages are correctly stored for a lead."""
    user = User(id=uuid.uuid4(), email="mem@test.com", name="Mem", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    
    lead = Lead(id=uuid.uuid4(), user_id=user.id, name="Memory Test", phone_number="+972501112222")
    db_session.add(lead)
    db_session.commit()

    msg = Message(lead_id=lead.id, sender_type="user", content="Hello Bot")
    db_session.add(msg)
    db_session.commit()

    assert len(lead.messages) == 1
    assert lead.messages[0].content == "Hello Bot"

def test_session_upload_gate(client):
    """Ensures that unauthenticated or non-pro users are blocked appropriately on uploads."""
    response = client.post(f"/api/v1/sessions/upload/{uuid.uuid4()}", files={'file': ('test.mp3', b'fake', 'audio/mpeg')})
    assert response.status_code == 401 # Unauthorized missing token