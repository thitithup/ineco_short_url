import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.database import Base, get_db
from src.models import URLItem
from src.config import settings

# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_shorten_url_auth_failure(client):
    # Missing header
    res1 = client.post("/api/v1/shorten", json={"original_url": "https://ineco.tech"})
    assert res1.status_code == 401
    assert res1.json()["error_code"] == "MISSING_API_KEY"

    # Invalid header
    res2 = client.post(
        "/api/v1/shorten",
        json={"original_url": "https://ineco.tech"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert res2.status_code == 403
    assert res2.json()["error_code"] == "INVALID_API_KEY"


def test_shorten_url_success(client):
    payload = {
        "original_url": "https://google.com/search?q=fastapi",
        "expires_in_hours": 48,
    }
    response = client.post(
        "/api/v1/shorten",
        json=payload,
        headers={"X-API-Key": settings.API_KEY},
    )
    assert response.status_code == 201
    data = response.json()
    assert "short_code" in data
    assert len(data["short_code"]) == 6
    assert data["original_url"] == payload["original_url"]
    assert data["expires_at"] is not None


def test_redirect_and_analytics_counter(client):
    # 1. Create short URL
    create_res = client.post(
        "/api/v1/shorten",
        json={"original_url": "https://github.com"},
        headers={"X-API-Key": settings.API_KEY},
    )
    code = create_res.json()["short_code"]

    # 2. Visit redirect endpoint
    redirect_res = client.get(f"/{code}", follow_redirects=False)
    assert redirect_res.status_code == 307
    assert redirect_res.headers["location"] == "https://github.com"

    # Visit again
    client.get(f"/{code}", follow_redirects=False)

    # 3. Check analytics
    analytics_res = client.get(
        f"/api/v1/analytics/{code}",
        headers={"X-API-Key": settings.API_KEY},
    )
    assert analytics_res.status_code == 200
    analytics = analytics_res.json()
    assert analytics["total_clicks"] == 2
    assert analytics["is_expired"] is False
    assert len(analytics["recent_clicks"]) == 2


def test_redirect_expired_url(client):
    db = TestingSessionLocal()
    expired_item = URLItem(
        original_url="https://expired-site.com",
        short_code="exp123",
        click_count=0,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db.add(expired_item)
    db.commit()
    db.close()

    res = client.get("/exp123", follow_redirects=False)
    assert res.status_code == 410
    assert res.json()["error_code"] == "URL_EXPIRED"


def test_redirect_not_found(client):
    res = client.get("/nonexistent", follow_redirects=False)
    assert res.status_code == 404
    assert res.json()["error_code"] == "URL_NOT_FOUND"


def test_get_qr_code_success(client):
    # 1. Create short URL
    create_res = client.post(
        "/api/v1/shorten",
        json={"original_url": "https://example.com/target-qr"},
        headers={"X-API-Key": settings.API_KEY},
    )
    code = create_res.json()["short_code"]

    # 2. Get QR code
    qr_res = client.get(f"/api/v1/qrcode/{code}")
    assert qr_res.status_code == 200
    assert qr_res.headers["content-type"] == "image/png"
    # Verify PNG magic bytes
    assert qr_res.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(qr_res.content) > 100


def test_get_qr_code_not_found(client):
    res = client.get("/api/v1/qrcode/notfound")
    assert res.status_code == 404
    assert res.json()["error_code"] == "URL_NOT_FOUND"


def test_get_qr_code_expired(client):
    db = TestingSessionLocal()
    expired_item = URLItem(
        original_url="https://expired-qr.com",
        short_code="qrexp1",
        click_count=0,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db.add(expired_item)
    db.commit()
    db.close()

    res = client.get("/api/v1/qrcode/qrexp1")
    assert res.status_code == 410
    assert res.json()["error_code"] == "URL_EXPIRED"

