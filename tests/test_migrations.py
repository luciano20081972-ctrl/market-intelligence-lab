from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from packages.core.config import EXPECTED_SCHEMA_REVISION, get_settings


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
    assert "worker_instances" in tables
    assert "reconciliation_runs" in tables
    assert "workspaces" in tables
    assert "provider_comparisons" in tables
    assert "backtest_reproducibility_manifests" in tables
    command.check(config)
    get_settings.cache_clear()


def test_upgrade_from_v03_schema_preserves_existing_data(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "v03-upgrade.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("MIL_DATABASE_URL", database_url)  # type: ignore[attr-defined]
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "10fdd3577a14")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO providers (
                    id, code, name, adapter_type, capabilities, configuration,
                    credential_environment_keys, is_enabled, health, created_at, updated_at
                ) VALUES (
                    :id, 'preserved', 'Preserved Provider', 'DisabledProviderAdapter',
                    '[]', '{}', '[]', 0, 'disabled', :created, :created
                )
                """
            ),
            {"id": "12345678123456781234567812345678", "created": "2026-01-01 00:00:00"},
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT code FROM providers WHERE code = 'preserved'"))
            == "preserved"
        )
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == EXPECTED_SCHEMA_REVISION
        )
    command.check(config)
    engine.dispose()
    get_settings.cache_clear()


def test_v05_to_v051_lockdown_upgrade_preserves_existing_data(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "v05-upgrade.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("MIL_DATABASE_URL", database_url)  # type: ignore[attr-defined]
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "18cca98a50d5")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO watchlists "
                "(id,workspace_id,name,description,created_at,updated_at) "
                "VALUES (:id,:workspace_id,'Preserved v0.5','release rehearsal',"
                "'2026-07-30','2026-07-30')"
            ),
            {
                "id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "workspace_id": "00000000000040008000000000000002",
            },
        )
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(
            text("SELECT name FROM watchlists WHERE name='Preserved v0.5'")
        ) == "Preserved v0.5"
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            EXPECTED_SCHEMA_REVISION
        )
    command.check(config)
    engine.dispose()
    get_settings.cache_clear()


def test_v06_to_v07_upgrade_preserves_sec_data(tmp_path: Path, monkeypatch: object) -> None:
    database = tmp_path / "v06-upgrade.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("MIL_DATABASE_URL", database_url)  # type: ignore[attr-defined]
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "6b8d9e0f1a2b")
    engine = create_engine(database_url)
    company_id = "cccccccccccccccccccccccccccccccc"
    checksum = "a" * 64
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sec_companies "
                "(id,cik,name,tickers,submissions_url,facts_url,retrieved_at,source_checksum) "
                "VALUES (:id,'0000320193','Preserved SEC','[]','https://data.sec.gov/a',"
                "'https://data.sec.gov/b','2026-08-01',:checksum)"
            ),
            {"id": company_id, "checksum": checksum},
        )
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(
            text("SELECT name FROM sec_companies WHERE id=:id"), {"id": company_id}
        ) == "Preserved SEC"
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            EXPECTED_SCHEMA_REVISION
        )
    command.check(config)
    engine.dispose()
    get_settings.cache_clear()


def test_postgresql_offline_sql_contains_only_public_application_lockdown(
    monkeypatch: object,
) -> None:
    monkeypatch.setenv(  # type: ignore[attr-defined]
        "MIL_DATABASE_URL", "postgresql+psycopg://migration:placeholder@localhost/postgres"
    )
    get_settings.cache_clear()
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    command.upgrade(config, "head", sql=True)
    rendered = output.getvalue()
    assert 'ALTER TABLE public."assets" ENABLE ROW LEVEL SECURITY' in rendered
    assert "REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC" in rendered
    assert "ALTER DEFAULT PRIVILEGES IN SCHEMA public" in rendered
    assert "::VARCHAR" not in rendered
    assert (
        "UPDATE watchlists SET workspace_id = "
        "'00000000-0000-4000-8000-000000000002'" in rendered
    )
    for index_name in (
        "ix_backtest_trades_source_price_bar_id",
        "ix_paper_fills_source_price_bar_id",
        "ix_paper_orders_source_price_bar_id",
        "ix_signals_source_price_bar_id",
    ):
        assert f"CREATE INDEX {index_name}" in rendered
    assert not any(
        f"{schema}." in rendered
        for schema in ("auth", "storage", "realtime", "vault", "supabase_migrations")
    )
    get_settings.cache_clear()


def test_v041_existing_data_moves_to_idempotent_legacy_workspace(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "v041-upgrade.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("MIL_DATABASE_URL", database_url)  # type: ignore[attr-defined]
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "1a52c2d25013")
    engine = create_engine(database_url)
    watchlist_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO watchlists (id,name,description,created_at,updated_at) "
                "VALUES (:id,'Preserved Watchlist','legacy','2026-01-01','2026-01-01')"
            ),
            {"id": watchlist_id},
        )
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name, workspace_id FROM watchlists WHERE id=:id"),
            {"id": watchlist_id},
        ).one()
        assert row.name == "Preserved Watchlist"
        assert row.workspace_id == "00000000000040008000000000000002"
        assert connection.scalar(text("SELECT count(*) FROM workspaces")) == 1
        assert connection.scalar(text("SELECT count(*) FROM workspace_memberships")) == 1
    command.check(config)
    engine.dispose()
    get_settings.cache_clear()
