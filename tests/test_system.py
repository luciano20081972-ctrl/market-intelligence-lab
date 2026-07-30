from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect

from apps.api.main import create_app
from packages.core.config import Settings


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "healthy", "version": "0.5.0"}


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
    settings = Settings(database_url="postgresql://analyst:super-secret@database/research")
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
