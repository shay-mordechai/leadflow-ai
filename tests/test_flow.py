import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

# --- IMPORTS ---
from src.main import app
from src.database.session import Base, get_db
import src.database.models 

# --- CONFIG FOR TESTING ---
# Use StaticPool to keep in-memory DB alive, but reset per test function
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_engine():
    """
    Creates a fresh in-memory database engine for each test function.
    """
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
    """
    Creates a fresh session for each test.
    """
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def client(db_session):
    """
    Overrides the get_db dependency to use the fresh test session.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass # Session closed by fixture

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

# --- TESTS ---

def test_auth_flow(client):
    """
    Tests the full registration -> login -> OTP flow.
    """
    # 1. Register
    # Using a password > 12 chars to pass validation
    password = "YourPassword123!" 
    
    reg_response = client.post("/api/v1/auth/register", json={
        "email": "test@user.com",
        "password": password,
        "full_name": "Test User",
        "business_name": "Test Biz",
        "business_type": "Tech",
        "plan_tier": "PRO"
    })
    assert reg_response.status_code == 201, f"Registration failed: {reg_response.text}"

    # 2. Login (Trigger OTP)
    with patch("src.routers.auth.send_otp_email") as mock_email:
        login_response = client.post("/api/v1/auth/login", data={"username": "test@user.com", "password": password})
        
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        assert mock_email.called, "OTP Email should be called on login"
        
        args = mock_email.call_args[0]
        otp_code = args[1]

    # 3. Verify OTP
    verify_response = client.post("/api/v1/auth/verify-otp", json={
        "email": "test@user.com", 
        "otp_code": otp_code
    })
    
    assert verify_response.status_code == 200
    token = verify_response.json().get("access_token")
    assert token is not None

def test_security_purchase_gate(client):
    """
    Ensures that users on STARTER plan cannot access PRO features (Phone Purchase).
    """
    # Setup: Create Starter User
    email = "starter@gate.com"
    # Using a password > 12 chars to pass validation
    password = "YourPassword123!"
    
    reg_res = client.post("/api/v1/auth/register", json={
        "email": email, 
        "password": password, 
        "full_name": "Gate",
        "business_name": "B", 
        "business_type": "T", 
        "plan_tier": "starter" 
    })
    # Assert registration success before trying to login
    assert reg_res.status_code == 201, f"Starter registration failed: {reg_res.text}"

    # Login Flow Helper
    with patch("src.routers.auth.send_otp_email") as mock:
        login_res = client.post("/api/v1/auth/login", data={"username": email, "password": password})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        
        assert mock.called, "OTP Email was not triggered"
        otp = mock.call_args[0][1]

    # Verify & Get Token
    verify = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp})
    assert verify.status_code == 200
    token = verify.json()["access_token"]

    # Attempt to buy phone number (Should Fail - 403 Forbidden)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/v1/phones/purchase", 
                         json={"phone_number": "+972509999999"},
                         headers=headers)
    
    # Assert
    assert response.status_code == 403
    assert "restricted to PRO" in response.json()["detail"]