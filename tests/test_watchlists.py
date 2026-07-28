from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from packages.database.models import AuditEvent, Watchlist, WatchlistAsset
from packages.database.session import make_session_factory, session_scope


def _create(client: TestClient, name: str = "Core holdings") -> dict[str, object]:
    response = client.post("/api/v1/watchlists", json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_watchlist_creation_and_listing(client: TestClient) -> None:
    created = _create(client)
    listed = client.get("/api/v1/watchlists").json()
    assert created["name"] == "Core holdings"
    assert [item["id"] for item in listed] == [created["id"]]


def test_watchlist_rename(client: TestClient) -> None:
    created = _create(client)
    response = client.patch(f"/api/v1/watchlists/{created['id']}", json={"name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


def test_watchlist_deletion(client: TestClient) -> None:
    created = _create(client)
    assert client.delete(f"/api/v1/watchlists/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/watchlists/{created['id']}").status_code == 404


def test_add_and_remove_asset_with_symbol_normalization(client: TestClient) -> None:
    created = _create(client)
    path = f"/api/v1/watchlists/{created['id']}/assets"
    added = client.post(path, json={"symbol": "aapl"})
    assert added.status_code == 200
    assert added.json()["assets"][0]["symbol"] == "AAPL"
    removed = client.delete(f"{path}/aapl")
    assert removed.status_code == 200
    assert removed.json()["assets"] == []


def test_duplicate_watchlist_asset_prevention(client: TestClient) -> None:
    created = _create(client)
    path = f"/api/v1/watchlists/{created['id']}/assets"
    assert client.post(path, json={"symbol": "MSFT"}).status_code == 200
    duplicate = client.post(path, json={"symbol": "MSFT"})
    assert duplicate.status_code == 409
    assert "already" in duplicate.json()["detail"]


def test_duplicate_watchlist_name_prevention(client: TestClient) -> None:
    _create(client)
    duplicate = client.post("/api/v1/watchlists", json={"name": "Core holdings"})
    assert duplicate.status_code == 409


def test_invalid_asset_handling(client: TestClient) -> None:
    created = _create(client)
    response = client.post(f"/api/v1/watchlists/{created['id']}/assets", json={"symbol": "NOPE"})
    assert response.status_code == 404


def test_watchlist_cascade_behavior(client: TestClient, engine: Engine) -> None:
    created = _create(client)
    client.post(f"/api/v1/watchlists/{created['id']}/assets", json={"symbol": "QQQ"})
    client.delete(f"/api/v1/watchlists/{created['id']}")
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        assert session.scalar(select(func.count(WatchlistAsset.id))) == 0
        assert session.scalar(select(func.count(Watchlist.id))) == 0


def test_audit_event_creation(client: TestClient, engine: Engine) -> None:
    created = _create(client)
    client.post(f"/api/v1/watchlists/{created['id']}/assets", json={"symbol": "NVDA"})
    client.delete(f"/api/v1/watchlists/{created['id']}/assets/NVDA")
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        actions = session.scalars(select(AuditEvent.action).order_by(AuditEvent.occurred_at)).all()
    assert actions == ["watchlist.created", "watchlist.asset_added", "watchlist.asset_removed"]


def test_request_validation(client: TestClient) -> None:
    response = client.post("/api/v1/watchlists", json={"name": "   "})
    assert response.status_code == 422
    response = client.post("/api/v1/watchlists", json={"name": "x" * 101})
    assert response.status_code == 422
