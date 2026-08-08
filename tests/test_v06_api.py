from __future__ import annotations


def test_sec_fixture_workflow_is_idempotent(client) -> None:  # type: ignore[no-untyped-def]
    payload = {
        "cik": "320193",
        "forms": ["10-K", "4", "13F-HR"],
        "mode": "fixture",
        "idempotency_key": "sec-fixture-v06",
    }
    first = client.post("/api/v1/sec/imports", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/sec/imports", json=payload)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert client.get("/api/v1/sec/companies").json()["total"] == 1
    filings = client.get("/api/v1/sec/filings").json()
    assert filings["total"] == 3
    detail = client.get(f"/api/v1/sec/filings/{filings['items'][0]['id']}")
    assert detail.status_code == 200
    assert client.get("/api/v1/sec/insider-transactions").json()["total"] == 1
    assert client.get("/api/v1/sec/institutional-holdings").json()["total"] == 1


def test_analytics_optimization_and_lean_fixture_apis(client) -> None:  # type: ignore[no-untyped-def]
    analytics = client.post(
        "/api/v1/analytics/compare",
        json={
            "returns": [0.01, -0.005, 0.007, 0.002],
            "benchmark_returns": [0.005, -0.002, 0.004, 0.001],
            "period_start": "2026-01-01",
            "period_end": "2026-02-01",
            "benchmark": "SPY",
            "tolerance": 0.000001,
        },
    )
    assert analytics.status_code == 201
    assert analytics.json()["agreement_status"] == "agrees"
    optimization = client.post(
        "/api/v1/optimization/experiments",
        json={
            "model": "minimum_variance",
            "asset_returns": {
                "AAA": [0.01, -0.005, 0.007, 0.002],
                "BBB": [0.002, 0.004, -0.001, 0.006],
            },
            "training_start": "2025-01-01",
            "training_end": "2025-09-30",
            "validation_start": "2025-10-01",
            "validation_end": "2025-12-31",
        },
    )
    assert optimization.status_code == 201
    assert sum(optimization.json()["weights"].values()) == 1
    status = client.get("/api/v1/upstream/engines/lean")
    assert status.status_code == 200
    lean = client.post(
        "/api/v1/upstream/engines/lean/fixture",
        json={
            "strategy": "buy_and_hold",
            "symbols": ["AAPL"],
            "start": "2025-01-01",
            "end": "2025-12-31",
            "initial_cash": "10000",
            "fee_per_order": "1",
            "slippage_bps": "5",
            "live_mode": False,
        },
    )
    assert lean.status_code == 201
    assert lean.json()["manifest"]["brokerage_credentials"] is False


def test_upstream_status_and_license_labels(client) -> None:  # type: ignore[no-untyped-def]
    integrations = client.get("/api/v1/upstream/integrations")
    assert integrations.status_code == 200
    assert integrations.json()["contains_secrets"] is False
    licenses = client.get("/api/v1/upstream/licenses")
    assert licenses.status_code == 200
    categories = {item["integration_category"] for item in licenses.json()["items"]}
    assert {"dependency", "optional_engine", "reference_only"} <= categories


def test_v06_api_rejects_unsafe_inputs(client) -> None:  # type: ignore[no-untyped-def]
    assert client.post(
        "/api/v1/upstream/engines/lean/fixture",
        json={
            "strategy": "buy_and_hold",
            "symbols": ["AAPL"],
            "start": "2025-01-01",
            "end": "2025-12-31",
            "initial_cash": "10000",
            "fee_per_order": "1",
            "slippage_bps": "5",
            "live_mode": True,
        },
    ).status_code == 422
    assert client.post(
        "/api/v1/optimization/experiments",
        json={
            "model": "minimum_variance",
            "asset_returns": {"AAA": [0.1, 0.2, 0.3], "BBB": [0.2, 0.1, 0.0]},
            "training_start": "2025-01-01",
            "training_end": "2025-12-01",
            "validation_start": "2025-11-01",
            "validation_end": "2025-12-31",
        },
    ).status_code == 422
