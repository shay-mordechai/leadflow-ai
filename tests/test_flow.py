import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 1. Setup Environment BEFORE importing app
os.environ["SECRET_KEY"] = "test_secret_key_for_jwt_generation_123"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_ENV"] = "testing"

from src.main import app
from src.database.session import get_db
from src.database.models import Base, User, PlanTier
from src.security.hashing import verify_hash

# 2. In-Memory Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(setup_db):
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="module")
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

def test_auth_flow(client, db_session):
    email = "test@user.com"
    password = "StrongPassword123!"
    
    # A. Register
    response = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Test User",
        "business_name": "Yoga",
        "business_type": "Yoga",
        "plan_tier": "starter"
    })
    assert response.status_code == 201
    
    # B. Verify Hashing
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.hashed_password != password
    assert verify_hash(password, user.hashed_password)

    # C. Login & Mock OTP
    with patch("src.routers.auth.send_otp_email") as mock_email:
        response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
        assert response.status_code == 200
        
        # Extract OTP from Mock call arguments
        args, _ = mock_email.call_args
        otp_code = args[1] 

    # D. Verify & Get Token
    response = client.post("/api/v1/auth/verify-otp", json={
        "email": email, "otp_code": otp_code
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert token is not None
    return token

def test_security_purchase_gate(client, db_session):
    # Setup: Create Starter User
    email = "starter@gate.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "Pass123!", "full_name": "Gate", 
        "business_name": "B", "business_type": "T", "plan_tier": "starter"
    })
    
    # Login Flow Helper
    with patch("src.routers.auth.send_otp_email") as mock:
        client.post("/api/v1/auth/login", data={"username": email, "password": "Pass123!"})
        otp = mock.call_args[0][1]
    
    token = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Attempt Purchase as STARTER -> Should Fail (403)
    res = client.post("/api/v1/phones/purchase", 
                      json={"phone_number": "+972500000000", "country_code": "IL"},
                      headers=headers)
    assert res.status_code == 403

    # 2. Upgrade to PRO (Direct DB Manipulation)
    user = db_session.query(User).filter(User.email == email).first()
    user.plan_tier = PlanTier.PRO
    db_session.commit()

    # 3. Attempt Purchase as PRO -> Should Succeed
    # Mock Twilio to avoid real purchase
    with patch("src.services.providers.twilio.twilio_provider.buy_number", return_value="MN123"):
        res = client.post("/api/v1/phones/purchase", 
                          json={"phone_number": "+972500000000", "country_code": "IL"},
                          headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "success"
