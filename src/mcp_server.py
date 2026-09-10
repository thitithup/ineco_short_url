"""
Model Context Protocol (MCP) Server for Ineco Short URL Generator.
Provides tools and resources for AI Agents to shorten URLs, query analytics,
and inspect target URLs via standard I/O (stdio).
"""

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional, Generator
from sqlalchemy.orm import Session

from urllib.parse import urlparse

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as MCPServer

from src.database import SessionLocal, Base, engine
from src.models import URLItem, ClickLog
from src.schemas import URLCreate
from src.config import settings
from src import crud

# Initialize database schema if not already present
Base.metadata.create_all(bind=engine)

# Instantiate MCP Server
mcp = MCPServer(
    name="ineco-short-url-mcp",
    instructions="MCP Server for URL shortening, safe destination resolution, and click analytics.",
)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session for MCP tool invocations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@mcp.tool(
    description="Shorten a target long URL and optionally specify expiration time in hours."
)
def shorten_url(url: str, expires_in_hours: Optional[int] = None) -> dict:
    """
    Create a new shortened URL.

    Args:
        url: The original destination URL (must be valid HTTP/HTTPS URL).
        expires_in_hours: Optional lifetime in hours before the URL expires.

    Returns:
        A dictionary containing short_code, short_url, original_url, and expiration details.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {
            "status": "error",
            "error_code": "INVALID_URL_INPUT",
            "message": "URL must be a valid web address starting with http:// or https://",
        }

    try:
        url_in = URLCreate(original_url=url, expires_in_hours=expires_in_hours)
    except Exception as exc:
        return {
            "status": "error",
            "error_code": "INVALID_URL_INPUT",
            "message": str(exc),
        }

    with get_db_session() as db:
        item = crud.create_short_url(db, url_in)
        short_url = f"{settings.BASE_URL}/{item.short_code}"
        return {
            "status": "success",
            "short_code": item.short_code,
            "short_url": short_url,
            "original_url": item.original_url,
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }


@mcp.tool(
    description="Safely inspect the destination of a short code without incrementing click counts."
)
def resolve_url(short_code: str) -> dict:
    """
    Resolve a short code to its original URL for safety verification.
    This operation does NOT trigger a redirection or increase the click counter.

    Args:
        short_code: The 6-character short code.

    Returns:
        A dictionary containing destination URL and expiration status.
    """
    with get_db_session() as db:
        item = crud.get_url_by_code(db, short_code)
        if not item:
            return {
                "status": "error",
                "error_code": "URL_NOT_FOUND",
                "message": f"Short URL code '{short_code}' not found.",
            }

        is_expired = crud.is_url_expired(item)
        return {
            "status": "success",
            "short_code": item.short_code,
            "original_url": item.original_url,
            "is_expired": is_expired,
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        }


@mcp.tool(
    description="Retrieve click counts, creation date, expiration status, and recent click logs for a short URL."
)
def get_url_analytics(short_code: str) -> dict:
    """
    Retrieve aggregated analytics and recent click records for a short code.

    Args:
        short_code: The 6-character short code.

    Returns:
        A dictionary containing total clicks, expiration status, and recent click log history.
    """
    with get_db_session() as db:
        item = crud.get_url_by_code(db, short_code)
        if not item:
            return {
                "status": "error",
                "error_code": "URL_NOT_FOUND",
                "message": f"Short URL code '{short_code}' not found.",
            }

        is_expired = crud.is_url_expired(item)
        recent_clicks = [
            {
                "clicked_at": log.clicked_at.isoformat() if log.clicked_at else None,
                "user_agent": log.user_agent,
                "referrer": log.referrer,
            }
            for log in item.click_logs[:10]
        ]

        return {
            "status": "success",
            "short_code": item.short_code,
            "original_url": item.original_url,
            "total_clicks": item.click_count,
            "is_expired": is_expired,
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "recent_clicks": recent_clicks,
        }


@mcp.resource("short://recent-urls")
def get_recent_urls() -> str:
    """
    Resource providing the 10 most recently created short URLs with metadata.

    Returns:
        JSON string containing the list of recent URLs.
    """
    with get_db_session() as db:
        items = db.query(URLItem).order_by(URLItem.created_at.desc()).limit(10).all()
        data = [
            {
                "short_code": item.short_code,
                "original_url": item.original_url,
                "total_clicks": item.click_count,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            }
            for item in items
        ]
        return json.dumps(data, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
