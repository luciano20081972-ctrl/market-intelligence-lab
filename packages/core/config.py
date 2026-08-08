from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EXPECTED_SCHEMA_REVISION = "2f9e39afd435"


def normalize_database_url(value: str) -> str:
    """Select the installed psycopg v3 SQLAlchemy dialect without exposing the URL."""

    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


class Settings(BaseSettings):
    """Environment-only configuration; secret values are never exposed by the API."""

    model_config = SettingsConfigDict(
        env_prefix="MIL_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Market Intelligence Lab"
    version: str = "0.9.0"
    environment: str = "development"
    database_url: str = "sqlite:///./data/market_intelligence.db"
    migration_database_url: str | None = None
    expected_schema_revision: str = EXPECTED_SCHEMA_REVISION
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    web_host: str = "127.0.0.1"
    web_port: int = Field(default=5173, ge=1, le=65535)
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    seed_demo_data: bool = True
    worker_poll_interval: float = Field(default=2.0, ge=0.1, le=300)
    worker_lease_seconds: int = Field(default=60, ge=10, le=3600)
    stooq_timeout_seconds: float = Field(default=10.0, ge=1, le=60)
    json_logs: bool = False
    expensive_request_limit_per_minute: int = Field(default=10, ge=1, le=1000)
    auth_mode: str = "disabled"
    supabase_project_ref: str | None = None
    supabase_url: str | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_publishable_key: str | None = None
    supabase_secret_key: str | None = None
    run_live_supabase_tests: bool = False
    twelve_data_api_key: str | None = None
    trusted_hosts: list[str] = ["127.0.0.1", "localhost", "testserver"]
    max_request_bytes: int = Field(default=1_000_000, ge=1_024, le=10_000_000)
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0, le=1)
    sec_user_agent: str = "Market Intelligence Lab research@example.invalid"
    sec_requests_per_second: float = Field(default=4.0, gt=0, le=10)
    sec_timeout_seconds: float = Field(default=20.0, ge=1, le=60)
    run_live_sec_tests: bool = False
    fred_api_key: str | None = None
    eia_api_key: str | None = None
    raw_object_store_root: str = "data/raw"
    run_live_world_data_tests: bool = False
    lean_executable: str | None = None

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def validate_database_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith(("sqlite://", "postgresql://", "postgresql+psycopg://")):
            raise ValueError("Database URLs must use SQLite or PostgreSQL")
        return normalize_database_url(value)

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("https://"):
            raise ValueError("MIL_SUPABASE_URL must use HTTPS")
        return value

    @field_validator("auth_mode")
    @classmethod
    def validate_auth_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"disabled", "supabase"}:
            raise ValueError("MIL_AUTH_MODE must be disabled or supabase")
        return normalized

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        if self.environment.lower() == "production" and self.auth_mode == "disabled":
            raise ValueError("MIL_AUTH_MODE=disabled is forbidden in production")
        if self.auth_mode == "supabase" and not self.supabase_url:
            raise ValueError("MIL_SUPABASE_URL is required when Supabase authentication is enabled")
        return self

    def ensure_runtime_directories(self, root: Path | None = None) -> None:
        project_root = root or Path.cwd()
        if self.database_url.startswith("sqlite"):
            database_path = self.database_url.split("///", maxsplit=1)[-1]
            if database_path != ":memory:":
                path = Path(database_path)
                if not path.is_absolute():
                    path = project_root / path
                path.parent.mkdir(parents=True, exist_ok=True)

    def public_summary(self) -> dict[str, str | bool]:
        return {
            "app_name": self.app_name,
            "version": self.version,
            "environment": self.environment,
            "database_engine": self.database_url.split(":", maxsplit=1)[0].split("+", maxsplit=1)[
                0
            ],
            "demonstration_mode": self.seed_demo_data,
            "authentication_mode": self.auth_mode,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
