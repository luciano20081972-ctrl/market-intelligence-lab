from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-only configuration; secret values are never exposed by the API."""

    model_config = SettingsConfigDict(
        env_prefix="MIL_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Market Intelligence Lab"
    version: str = "0.2.0"
    environment: str = "development"
    database_url: str = "sqlite:///./data/market_intelligence.db"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    web_host: str = "127.0.0.1"
    web_port: int = Field(default=5173, ge=1, le=65535)
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    seed_demo_data: bool = True

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("sqlite://", "postgresql://", "postgresql+psycopg://")):
            raise ValueError("MIL_DATABASE_URL must use SQLite or PostgreSQL")
        return value

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
            "database_engine": self.database_url.split(":", maxsplit=1)[0],
            "demonstration_mode": self.seed_demo_data,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
