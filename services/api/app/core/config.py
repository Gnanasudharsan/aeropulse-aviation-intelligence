from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Look for a .env in the package ancestors (repo root locally); absent in containers.
_ENV_FILES = tuple(str(d / ".env") for d in reversed(Path(__file__).resolve().parents[:5]))


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment variables / `.env`."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://aeropulse:change-me-locally@localhost:5442/aeropulse"
    db_pool_size: int = 5
    db_max_overflow: int = 5

    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    rate_limit_per_minute: int = 120
    ingest_trigger_token: str = ""

    http_user_agent: str = (
        "AeroPulse/1.0 (+https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence)"
    )
    http_timeout_seconds: float = 15.0
    http_max_retries: int = 3
    http_retry_base_delay: float = 1.0

    faa_airport_events_url: str = "https://nasstatus.faa.gov/api/airport-events"
    faa_status_xml_url: str = "https://nasstatus.faa.gov/api/airport-status-information"
    awc_base_url: str = "https://aviationweather.gov/api/data"

    scheduler_enabled: bool = True
    faa_poll_seconds: int = 300
    metar_poll_seconds: int = 600
    taf_poll_seconds: int = 1800
    bronze_retention_days: int = 7

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("database_url")
    @classmethod
    def _normalise_driver(cls, v: str) -> str:
        # Hosted providers hand out postgres:// URLs; force the psycopg3 driver.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
