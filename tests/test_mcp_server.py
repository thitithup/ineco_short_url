import json
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models import URLItem
from src import mcp_server
from src import crud

# In-memory SQLite for test isolation
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_mcp_test_environment(monkeypatch):
    """Ensure in-memory database is used for all MCP tests."""
    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr(mcp_server, "SessionLocal", TestingSessionLocal)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_mcp_shorten_url_success():
    """Test successful URL shortening via MCP tool."""
    res = mcp_server.shorten_url("https://example.com/ineco-test")
    assert res["status"] == "success"
    assert "short_code" in res
    assert len(res["short_code"]) == 6
    assert res["original_url"] == "https://example.com/ineco-test"
    assert res["expires_at"] is None
    assert "http" in res["short_url"]


def test_mcp_shorten_url_with_expiration():
    """Test URL shortening with lifetime constraint."""
    res = mcp_server.shorten_url("https://example.com/expiring", expires_in_hours=24)
    assert res["status"] == "success"
    assert res["expires_at"] is not None


def test_mcp_shorten_url_invalid():
    """Test rejection of non-URL strings."""
    res = mcp_server.shorten_url("ftp://invalid-protocol")
    assert res["status"] == "error"
    assert res["error_code"] == "INVALID_URL_INPUT"


def test_mcp_resolve_url_success():
    """Test safe resolution of short code without incrementing clicks."""
    shorten_res = mcp_server.shorten_url("https://example.com/destination")
    code = shorten_res["short_code"]

    resolve_res = mcp_server.resolve_url(code)
    assert resolve_res["status"] == "success"
    assert resolve_res["original_url"] == "https://example.com/destination"
    assert resolve_res["is_expired"] is False

    # Verify click count was NOT increased (Safety Requirement)
    with mcp_server.get_db_session() as db:
        item = crud.get_url_by_code(db, code)
        assert item.click_count == 0


def test_mcp_resolve_url_not_found():
    """Test resolving a non-existent short code."""
    res = mcp_server.resolve_url("non999")
    assert res["status"] == "error"
    assert res["error_code"] == "URL_NOT_FOUND"


def test_mcp_resolve_url_expired():
    """Test resolving an expired short code."""
    with mcp_server.get_db_session() as db:
        past_time = datetime.now(timezone.utc) - timedelta(hours=2)
        item = URLItem(
            original_url="https://example.com/old",
            short_code="old001",
            click_count=0,
            expires_at=past_time,
        )
        db.add(item)
        db.commit()

    res = mcp_server.resolve_url("old001")
    assert res["status"] == "success"
    assert res["is_expired"] is True


def test_mcp_get_url_analytics_success():
    """Test retrieving click analytics and log history."""
    shorten_res = mcp_server.shorten_url("https://example.com/analytics-target")
    code = shorten_res["short_code"]

    # Simulate clicks
    with mcp_server.get_db_session() as db:
        item = crud.get_url_by_code(db, code)
        crud.record_click(db, item, user_agent="Antigravity-Agent/1.0", referrer="https://chat.ai")

    analytics_res = mcp_server.get_url_analytics(code)
    assert analytics_res["status"] == "success"
    assert analytics_res["total_clicks"] == 1
    assert len(analytics_res["recent_clicks"]) == 1
    assert analytics_res["recent_clicks"][0]["user_agent"] == "Antigravity-Agent/1.0"
    assert analytics_res["recent_clicks"][0]["referrer"] == "https://chat.ai"


def test_mcp_get_url_analytics_not_found():
    """Test analytics query on non-existent short code."""
    res = mcp_server.get_url_analytics("absent")
    assert res["status"] == "error"
    assert res["error_code"] == "URL_NOT_FOUND"


def test_mcp_resource_recent_urls():
    """Test MCP resource listing recent shortened URLs."""
    mcp_server.shorten_url("https://example.com/res1")
    mcp_server.shorten_url("https://example.com/res2")

    resource_json = mcp_server.get_recent_urls()
    data = json.loads(resource_json)
    assert isinstance(data, list)
    assert len(data) >= 2
    assert "short_code" in data[0]
    assert "original_url" in data[0]
