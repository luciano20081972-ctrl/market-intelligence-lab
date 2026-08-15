from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, text

from apps.api.main import create_app
from packages.core.config import Settings


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "healthy", "version": "0.14.0"}


def test_system_information(client: TestClient) -> None:
    data = client.get("/api/v1/system/info").json()
    assert data["tracked_assets"] == 9
    assert data["demonstration_bars"] == 1080
    assert data["database_health"] == "healthy"
    assert data["warning"] == "Synthetic demonstration data — not live market data."


def test_data_sources(client: TestClient) -> None:
    response = client.get("/api/v1/system/data-sources")
    assert response.status_code == 200
    source = response.json()[0]
    assert source["provider_type"] == "synthetic"
    assert source["stored_records"] == 1080
    assert "not licensed market data" in source["license_notes"]


def test_secret_redaction(engine: Engine) -> None:
    settings = Settings(database_url="postgresql://database.invalid/research")
    app = create_app(settings=settings, engine=engine)
    with TestClient(app) as test_client:
        content = test_client.get("/api/v1/system/info").text
    assert "super-secret" not in content
    assert "analyst" not in content
    assert "database/research" not in content
    assert '"database_engine":"postgresql"' in content


def test_schema_has_expected_tables(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) >= {
        "assets",
        "price_bars",
        "data_sources",
        "data_ingestion_runs",
        "watchlists",
        "watchlist_assets",
        "audit_events",
    }


def test_staging_readiness_requires_current_alembic_revision(engine: Engine) -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        environment="staging",
        auth_mode="supabase",
        supabase_url="https://project.supabase.co",
    )
    with TestClient(create_app(settings=settings, engine=engine)) as test_client:
        missing = test_client.get("/health/ready")
        assert missing.status_code == 503
        assert missing.json()["detail"]["code"] == "schema_unavailable"
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('18cca98a50d5')"))
    with TestClient(create_app(settings=settings, engine=engine)) as test_client:
        behind = test_client.get("/health/ready")
        assert behind.status_code == 503
        assert behind.json()["detail"]["code"] == "schema_outdated"
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE alembic_version SET version_num=:revision"),
            {"revision": settings.expected_schema_revision},
        )
    with TestClient(create_app(settings=settings, engine=engine)) as test_client:
        ready = test_client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["version"] == "0.14.0"


def test_postgresql_url_selects_installed_psycopg_driver() -> None:
    settings = Settings(database_url="postgresql://database.invalid/postgres")
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.public_summary()["database_engine"] == "postgresql"
    assert "placeholder" not in str(settings.public_summary())
