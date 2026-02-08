import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app
from src.database.session import Base, get_db
from unittest.mock import patch, MagicMock

# --- CONFIG FOR TESTING ---
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def client():
    # Setup DB
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    # Teardown
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    db = TestingSessionLocal()
    yield db
    db.close()

# --- TESTS ---

def test_auth_flow(client):
    # 1. Register
    reg_response = client.post("/api/v1/auth/register", json={
        "email": "test@user.com",
        "password": "StrongPassword123!",
        "full_name": "Test User",
        "business_name": "Test Biz",
        "business_type": "Tech",
        "plan_tier": "PRO"
    })
    assert reg_response.status_code == 201

    # 2. Login (Trigger OTP)
    # FIX: Correct patch path to where send_otp_email is actually imported in auth.py
    # Since auth.py imports 'send_otp_email', we must patch 'src.routers.auth.send_otp_email'
    with patch("src.routers.auth.send_otp_email") as mock_email:
        login_response = client.post("/api/v1/auth/login", data={"username": "test@user.com", "password": "StrongPassword123!"})
        assert login_response.status_code == 200
        assert mock_email.called
        
        # Get OTP from mock args
        args = mock_email.call_args[0] # (email, otp)
        otp_code = args[1]

    # 3. Verify OTP
    verify_response = client.post("/api/v1/auth/verify-otp", json={
        "email": "test@user.com", 
        "otp_code": otp_code
    })
    assert verify_response.status_code == 200
    token = verify_response.json()["access_token"]
    assert token is not None
    
    return token # Useful for dependency injection in other tests if needed

def test_security_purchase_gate(client, db_session):
    # Setup: Create Starter User
    email = "starter@gate.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "Pass123!", "full_name": "Gate",
        "business_name": "B", "business_type": "T", "plan_tier": "starter"
    })

    # Login Flow Helper
    # FIX: Patch the correct path in src.routers.auth
    with patch("src.routers.auth.send_otp_email") as mock:
        client.post("/api/v1/auth/login", data={"username": email, "password": "Pass123!"})
        
        # Assert called before accessing args
        assert mock.called, "OTP Email was not triggered"
        otp = mock.call_args[0][1]

    # Verify & Get Token
    verify = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp})
    token = verify.json()["access_token"]

    # Attempt to buy phone number (Should Fail - 403 Forbidden)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/v1/phones/purchase", 
                         json={"phone_number": "+972509999999"},
                         headers=headers)
    
    assert response.status_code == 403
    assert "restricted to PRO" in response.json()["detail"]