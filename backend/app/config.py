"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Google Sheets
    google_sheet_id: str = ""
    google_credentials_json: str = ""  # JSON string of service account creds

    # Auth
    app_pin: str = "1234"  # Override via fly secret
    jwt_secret: str = "change-me-in-production"  # Override via fly secret
    jwt_expiry_days: int = 7

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    debug: bool = False

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5175",
    ]
    cors_allow_all: bool = False

    # Cache
    cache_ttl_seconds: int = 30

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
