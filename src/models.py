from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class URLItem(Base):
    """URL Shortener database model."""

    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    original_url = Column(Text, nullable=False)
    short_code = Column(String(10), unique=True, index=True, nullable=False)
    click_count = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    click_logs = relationship(
        "ClickLog",
        back_populates="url_item",
        cascade="all, delete-orphan",
        order_by="desc(ClickLog.clicked_at)",
    )


class ClickLog(Base):
    """Click event tracking analytics model."""

    __tablename__ = "click_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url_id = Column(Integer, ForeignKey("urls.id", ondelete="CASCADE"), nullable=False, index=True)
    clicked_at = Column(DateTime, default=utc_now, nullable=False)
    user_agent = Column(Text, nullable=True)
    referrer = Column(Text, nullable=True)

    url_item = relationship("URLItem", back_populates="click_logs")
