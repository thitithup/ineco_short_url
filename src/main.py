from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from src.config import settings
from src.database import engine, Base, get_db
from src.auth import verify_api_key
from src.schemas import (
    URLCreate,
    URLResponse,
    AnalyticsResponse,
    ClickLogResponse,
    StandardErrorResponse,
)
from src import crud


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup: ensure database tables are created."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Short URL Generator API",
    description="High-performance URL Shortener and Analytics Service by Ineco Software House",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Enforce standard error response format on all HTTPExceptions."""
    if isinstance(exc.detail, dict) and "error_code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error_code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
            "details": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Standardize validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": "Invalid request parameters or payload",
            "details": exc.errors(),
        },
    )


@app.get("/health", tags=["Health"])
def health_check():
    """Service health verification endpoint."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}


@app.post(
    "/api/v1/shorten",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["URL Shortener"],
    responses={
        401: {"model": StandardErrorResponse},
        403: {"model": StandardErrorResponse},
        422: {"model": StandardErrorResponse},
    },
)
def shorten_url(
    payload: URLCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Generate a new short URL code for the target destination.
    Requires X-API-Key header.
    """
    db_item = crud.create_short_url(db, payload)
    short_url = f"{settings.BASE_URL.rstrip('/')}/{db_item.short_code}"

    return URLResponse(
        short_code=db_item.short_code,
        short_url=short_url,
        original_url=db_item.original_url,
        expires_at=db_item.expires_at,
        created_at=db_item.created_at,
    )


@app.get(
    "/{short_code}",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    tags=["Redirect"],
    responses={
        404: {"model": StandardErrorResponse},
        410: {"model": StandardErrorResponse},
    },
)
def redirect_short_url(
    short_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Redirect incoming visitor to the original URL and atomically record click analytics.
    Returns HTTP 410 if the link is expired, or 404 if not found.
    """
    url_item = crud.get_url_by_code(db, short_code)
    if not url_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "error_code": "URL_NOT_FOUND",
                "message": f"Short URL code '{short_code}' does not exist.",
            },
        )

    if crud.is_url_expired(url_item):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "status": "error",
                "error_code": "URL_EXPIRED",
                "message": f"The short URL '{short_code}' has expired on {url_item.expires_at}.",
            },
        )

    # Capture metadata
    user_agent = request.headers.get("user-agent")
    referrer = request.headers.get("referer")

    # Record analytics
    crud.record_click(db, url_item, user_agent=user_agent, referrer=referrer)

    return RedirectResponse(
        url=url_item.original_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@app.get(
    "/api/v1/analytics/{short_code}",
    response_model=AnalyticsResponse,
    tags=["Analytics"],
    responses={
        401: {"model": StandardErrorResponse},
        403: {"model": StandardErrorResponse},
        404: {"model": StandardErrorResponse},
    },
)
def get_analytics(
    short_code: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Retrieve click analytics, expiration state, and recent click history for a short URL.
    Requires X-API-Key header.
    """
    url_item = crud.get_url_by_code(db, short_code)
    if not url_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "error_code": "URL_NOT_FOUND",
                "message": f"Short URL code '{short_code}' was not found.",
            },
        )

    recent_clicks = [
        ClickLogResponse(
            clicked_at=log.clicked_at,
            user_agent=log.user_agent,
            referrer=log.referrer,
        )
        for log in url_item.click_logs[:50]
    ]

    return AnalyticsResponse(
        short_code=url_item.short_code,
        original_url=url_item.original_url,
        total_clicks=url_item.click_count,
        is_expired=crud.is_url_expired(url_item),
        expires_at=url_item.expires_at,
        recent_clicks=recent_clicks,
    )


@app.get(
    "/api/v1/qrcode/{short_code}",
    tags=["QR Code"],
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "High-resolution QR code image in PNG format",
        },
        404: {"model": StandardErrorResponse},
        410: {"model": StandardErrorResponse},
    },
)
def get_qr_code(
    short_code: str,
    box_size: int = 10,
    db: Session = Depends(get_db),
):
    """
    Generate and return a high-resolution QR Code image (PNG) for the short URL.
    Can be scanned directly by smartphones and QR readers.
    """
    url_item = crud.get_url_by_code(db, short_code)
    if not url_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "error_code": "URL_NOT_FOUND",
                "message": f"Short URL code '{short_code}' was not found.",
            },
        )

    if crud.is_url_expired(url_item):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "status": "error",
                "error_code": "URL_EXPIRED",
                "message": f"The short URL '{short_code}' has expired on {url_item.expires_at}.",
            },
        )

    short_url = f"{settings.BASE_URL.rstrip('/')}/{url_item.short_code}"
    clamped_size = max(2, min(box_size, 20))
    png_bytes = crud.generate_qr_code_png(short_url, box_size=clamped_size)

    return Response(content=png_bytes, media_type="image/png")

