import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment variables configuration."""

    DATABASE_URL: str = "sqlite:///./short_url.db"
    API_KEY: str = "ineco-secret-key-12345"
    BASE_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
