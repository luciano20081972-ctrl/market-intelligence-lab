from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from packages.core.config import get_settings


def test_clean_database_migration(tmp_path: Path, monkeypatch: object) -> None:
    database = tmp_path / "migration.db"
    monkeypatch.setenv("MIL_DATABASE_URL", f"sqlite:///{database.as_posix()}")  # type: ignore[attr-defined]
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    tables = set(inspect(create_engine(f"sqlite:///{database.as_posix()}")).get_table_names())
    assert "alembic_version" in tables
    assert "price_bars" in tables
    assert "watchlist_assets" in tables
    get_settings.cache_clear()
