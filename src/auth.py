from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from src.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Validate the incoming X-API-Key header against the configured system secret.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "error_code": "MISSING_API_KEY",
                "message": "Missing required X-API-Key header",
            },
        )

    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "error_code": "INVALID_API_KEY",
                "message": "The provided API key is invalid",
            },
        )

    return api_key
