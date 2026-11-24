"""Security and edge-case regression suite for billing, coupons, and payment webhooks."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import AuditLog, Lead, PlanTier, User
from src.database.session import Base, get_db
from src.main import app
from src.routers.billing import checkout
from src.routers.webhooks import meshulam
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
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def tenant_user(db_session):
    db_session.query(Lead).delete()
    db_session.query(AuditLog).delete()
    db_session.query(User).delete()
    db_session.commit()

    user = User(
        email="billing-tenant@my-leads.app",
        hashed_password=get_hash("StrongPass123!"),
        name="Billing Test Owner",
        business_name="Billing Clinic",
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
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = testing_session_local()
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


def test_coupon_100_percent_discount_immediate_upgrade(client, db_session, tenant_user):
    """100% coupon reduces payable total to 0.00 ILS and activates PRO without gateway redirect."""
    res = client.post("/api/v1/billing/apply-coupon", json={"coupon_code": "FREE100"})
    assert res.status_code == 200
    data = res.json()
    assert data["activated"] is True
    assert data["final_price"] == 0.0
    assert data["original_price"] == 199.0
    assert data["plan"] == "PRO"

    db_session.refresh(tenant_user)
    assert tenant_user.plan_tier == PlanTier.PRO

    log = db_session.query(AuditLog).filter(AuditLog.user_id == str(tenant_user.id)).first()
    assert log is not None
    assert log.action in ["COUPON_REDEEMED", "COUPON_ZERO_COST_ACTIVATION"]


def test_coupon_50_percent_and_decimal_precision(client):
    """50% coupon computes exact half-price amount with Decimal/agorot precision."""
    res = client.post("/api/v1/billing/apply-coupon", json={"coupon_code": "SAVE50"})
    assert res.status_code == 200
    data = res.json()
    assert data["activated"] is False
    assert data["discount_percent"] == 50
    assert data["original_price"] == 199.00
    assert data["final_price"] == 99.50


def test_client_side_price_tampering_ignored(client, db_session, tenant_user):
    """Tampered client fields (price=0, amount=1, discount_percent=100) cannot lower checkout sum."""
    mock_gateway_response = MagicMock(
        status_code=200,
        json=lambda: {
            "status": 1,
            "data": {
                "url": "https://sandbox.meshulam.co.il/pay/mock-session",
                "processId": "proc-123",
                "processToken": "tok-123",
            },
        },
    )

    with patch.object(
        httpx.AsyncClient,
        "post",
        new=AsyncMock(return_value=mock_gateway_response),
    ) as mock_post:
        res = client.post(
            "/api/v1/billing/create-payment",
            json={
                "plan": "PRO",
                "coupon_code": None,
                "price": 0,
                "amount": 1,
                "discount_percent": 100,
            },
        )

    assert res.status_code in [200, 422]
    if res.status_code == 200:
        data = res.json()
        assert data.get("final_price", 199.00) == 199.00
        assert mock_post.called
        sent_payload = str(mock_post.call_args)
        assert "199" in sent_payload

    db_session.refresh(tenant_user)
    assert tenant_user.plan_tier == PlanTier.FREE


def test_invalid_expired_exhausted_and_replayed_coupons(
    client, tenant_user, db_session, monkeypatch
):
    """Reject unknown, out-of-bounds, expired, exhausted, and replayed single-use coupons."""
    monkeypatch.setitem(
        checkout.ACTIVE_COUPONS,
        "OUTOFBOUNDS150",
        {"plan": "PRO", "discount_percent": 150, "days": 30, "desc": "Invalid >100%"},
    )
    monkeypatch.setitem(
        checkout.ACTIVE_COUPONS,
        "NEGATIVE20",
        {"plan": "PRO", "discount_percent": -20, "days": 30, "desc": "Invalid <0%"},
    )
    monkeypatch.setitem(
        checkout.ACTIVE_COUPONS,
        "EXPIRED100",
        {
            "plan": "PRO",
            "discount_percent": 100,
            "days": 30,
            "desc": "Expired",
            "expires_at": datetime.now(UTC) - timedelta(days=1),
        },
    )
    monkeypatch.setitem(
        checkout.ACTIVE_COUPONS,
        "EXHAUSTED100",
        {
            "plan": "PRO",
            "discount_percent": 100,
            "days": 30,
            "desc": "Exhausted",
            "max_uses": 1,
            "used_count": 1,
        },
    )
    monkeypatch.setitem(
        checkout.ACTIVE_COUPONS,
        "SINGLEUSE",
        {
            "plan": "PRO",
            "discount_percent": 100,
            "days": 30,
            "desc": "Single Use",
            "max_uses": 1,
            "used_count": 0,
        },
    )

    for bad_code in ("INVALID999", "OUTOFBOUNDS150", "NEGATIVE20", "EXPIRED100", "EXHAUSTED100"):
        resp = client.post("/api/v1/billing/apply-coupon", json={"coupon_code": bad_code})
        assert resp.status_code == 400, f"Expected 400 for {bad_code}, got {resp.status_code}"

    # First redemption succeeds
    first = client.post("/api/v1/billing/apply-coupon", json={"coupon_code": "SINGLEUSE"})
    assert first.status_code == 200
    assert first.json()["activated"] is True

    # Reset tier to simulate replay attempt by the same tenant
    tenant_user.plan_tier = PlanTier.FREE
    db_session.commit()

    replay = client.post("/api/v1/billing/apply-coupon", json={"coupon_code": "SINGLEUSE"})
    assert replay.status_code == 400


def test_direct_tier_escalation_guard(client, db_session, tenant_user):
    """Injecting plan_tier or tier into settings endpoints leaves the user locked at FREE."""
    res = client.post(
        "/api/v1/settings",
        json={
            "business_name": "Tampered Clinic",
            "business_type": "clinic",
            "plan_tier": "PRO",
            "tier": "PRO",
        },
    )
    assert res.status_code in [400, 422]

    db_session.refresh(tenant_user)
    assert tenant_user.plan_tier == PlanTier.FREE


def test_forged_unauthenticated_payment_webhook_guard(client, db_session, tenant_user):
    """Missing or forged HMAC signatures on payment webhooks return 403 without upgrading tier."""
    with patch.object(meshulam.settings, "MESHULAM_API_KEY", "secret-key-123"):
        forged_res = client.post(
            "/webhooks/meshulam/notify",
            data={
                "transactionId": "tx-forge-999",
                "sum": "199",
                "status": "1",
                "customField1": str(tenant_user.id),
                "signature": "forged_invalid_signature",
            },
        )
        assert forged_res.status_code == 403

        missing_sig_res = client.post(
            "/webhooks/meshulam/notify",
            data={
                "transactionId": "tx-forge-1000",
                "sum": "199",
                "status": "1",
                "customField1": str(tenant_user.id),
            },
        )
        assert missing_sig_res.status_code in [400, 401, 403, 422]

    db_session.refresh(tenant_user)
    assert tenant_user.plan_tier == PlanTier.FREE
