from decimal import Decimal

from fastapi.testclient import TestClient


def _strategy_version(client: TestClient, strategy_type: str = "buy_and_hold") -> str:
    items = client.get("/api/v1/strategies").json()["items"]
    return next(
        item["latest_version"]["id"] for item in items if item["strategy_type"] == strategy_type
    )


def _payload(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "strategy_version_id": _strategy_version(client),
        "symbols": ["AAPL", "MSFT"],
        "benchmark_symbol": "SPY",
        "start_time": "2025-01-02T21:00:00Z",
        "end_time": "2025-06-18T21:00:00Z",
        "initial_cash": "100000",
        "commission": "1",
        "spread_bps": "2",
        "slippage_bps": "1",
        "execution_delay": 1,
        "max_position_pct": "0.50",
        "max_total_exposure": "1.00",
    }
    payload.update(overrides)
    return payload


def test_backtest_shared_cash_metrics_and_provenance(client: TestClient) -> None:
    response = client.post("/api/v1/backtests", json=_payload(client))
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["is_hypothetical"] is True
    assert run["asset_symbols"] == ["AAPL", "MSFT"]
    assert Decimal(run["cash_balance"]) >= 0
    assert run["metrics"]["number_of_trades"] >= 2
    assert "benchmark_return" in run["metrics"]
    assert run["execution_assumptions"]["long_only"] is True
    assert run["data_source_identifiers"]
    curve = client.get(f"/api/v1/backtests/{run['id']}/equity-curve").json()
    assert len(curve) == 120
    assert max(Decimal(point["exposure"]) for point in curve) <= Decimal("1.000001")


def test_no_lookahead_and_delayed_execution(client: TestClient) -> None:
    first = client.post(
        "/api/v1/backtests", json=_payload(client, symbols=["AAPL"], execution_delay=1)
    ).json()
    second = client.post(
        "/api/v1/backtests", json=_payload(client, symbols=["AAPL"], execution_delay=2)
    ).json()
    trades_one = client.get(f"/api/v1/backtests/{first['id']}/trades").json()
    trades_two = client.get(f"/api/v1/backtests/{second['id']}/trades").json()
    assert trades_one and trades_two
    assert trades_one[0]["signal_time"] < trades_one[0]["execution_time"]
    assert trades_two[0]["execution_time"] > trades_one[0]["execution_time"]


def test_commission_spread_and_slippage_affect_results(client: TestClient) -> None:
    free = client.post(
        "/api/v1/backtests",
        json=_payload(client, symbols=["AAPL"], commission="0", spread_bps="0", slippage_bps="0"),
    ).json()
    costly = client.post(
        "/api/v1/backtests",
        json=_payload(
            client, symbols=["AAPL"], commission="10", spread_bps="20", slippage_bps="20"
        ),
    ).json()
    assert Decimal(costly["final_equity"]) < Decimal(free["final_equity"])
    costly_trades = client.get(f"/api/v1/backtests/{costly['id']}/trades").json()
    assert all(Decimal(trade["fees"]) == Decimal("10") for trade in costly_trades)


def test_position_and_total_exposure_limits(client: TestClient) -> None:
    run = client.post(
        "/api/v1/backtests",
        json=_payload(client, max_position_pct="0.10", max_total_exposure="0.15"),
    ).json()
    curve = client.get(f"/api/v1/backtests/{run['id']}/equity-curve").json()
    assert max(Decimal(point["exposure"]) for point in curve) <= Decimal("0.151")


def test_insufficient_shared_cash_is_safe(client: TestClient) -> None:
    response = client.post(
        "/api/v1/backtests",
        json=_payload(
            client,
            symbols=["AAPL"],
            initial_cash="10",
            commission="1000",
            max_position_pct="1",
        ),
    )
    assert response.status_code == 201
    assert Decimal(response.json()["cash_balance"]) == Decimal("10")
    assert response.json()["metrics"]["number_of_trades"] == 0


def test_backtest_validation_and_pagination(client: TestClient) -> None:
    invalid = client.post(
        "/api/v1/backtests", json=_payload(client, start_time="2025-02-01T00:00:00")
    )
    assert invalid.status_code == 422
    created = client.post("/api/v1/backtests", json=_payload(client)).json()
    listing = client.get("/api/v1/backtests?page=1&page_size=1").json()
    assert listing["total"] >= 1
    assert listing["items"][0]["id"] == created["id"]
