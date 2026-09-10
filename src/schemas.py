from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, HttpUrl, Field, ConfigDict


class URLCreate(BaseModel):
    """Schema for requesting a new short URL."""

    original_url: str = Field(..., description="Target destination URL", min_length=4)
    expires_in_hours: Optional[int] = Field(
        None,
        ge=1,
        le=87600,
        description="Optional expiration time in hours (max 10 years)",
    )


class URLResponse(BaseModel):
    """Schema returned after creating or querying a short URL."""

    short_code: str
    short_url: str
    original_url: str
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClickLogResponse(BaseModel):
    """Schema for a recorded click event."""

    clicked_at: datetime
    user_agent: Optional[str] = None
    referrer: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AnalyticsResponse(BaseModel):
    """Schema representing complete analytics for a short URL."""

    short_code: str
    original_url: str
    total_clicks: int
    is_expired: bool
    expires_at: Optional[datetime] = None
    recent_clicks: List[ClickLogResponse] = []

    model_config = ConfigDict(from_attributes=True)


class StandardErrorResponse(BaseModel):
    """Standardized error contract across all endpoints."""

    status: str = "error"
    error_code: str
    message: str
    details: Optional[Any] = None
