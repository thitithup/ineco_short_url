import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from src.models import URLItem, ClickLog
from src.schemas import URLCreate

ALPHABET = string.ascii_letters + string.digits  # Base62


def generate_short_code(length: int = 6) -> str:
    """Generate a cryptographically secure random base62 short code."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def get_url_by_code(db: Session, short_code: str) -> Optional[URLItem]:
    """Retrieve an active or expired URLItem by its short code."""
    return db.query(URLItem).filter(URLItem.short_code == short_code).first()


def is_url_expired(url_item: URLItem) -> bool:
    """Check if the URL item has exceeded its expiration timestamp."""
    if url_item.expires_at is None:
        return False
    # Ensure timezone awareness comparison
    now = datetime.now(timezone.utc)
    exp = url_item.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return now > exp


def create_short_url(db: Session, url_in: URLCreate) -> URLItem:
    """
    Create a new short URL item with collision resolution (max 5 retries).
    """
    expires_at = None
    if url_in.expires_in_hours is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=url_in.expires_in_hours)

    short_code = None
    for _ in range(5):
        candidate = generate_short_code(6)
        existing = get_url_by_code(db, candidate)
        if not existing:
            short_code = candidate
            break

    if not short_code:
        raise RuntimeError("Unable to generate unique short code after 5 attempts.")

    db_item = URLItem(
        original_url=str(url_in.original_url),
        short_code=short_code,
        click_count=0,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def record_click(
    db: Session,
    url_item: URLItem,
    user_agent: Optional[str] = None,
    referrer: Optional[str] = None,
) -> None:
    """Atomically increment the click count and log the click metadata."""
    url_item.click_count += 1
    click_log = ClickLog(
        url_id=url_item.id,
        clicked_at=datetime.now(timezone.utc),
        user_agent=user_agent,
        referrer=referrer,
    )
    db.add(click_log)
    db.commit()
    db.refresh(url_item)
