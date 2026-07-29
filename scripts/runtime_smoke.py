from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.main import create_app
from packages.core.config import get_settings
from packages.database.models import ImportJob, Provider
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.market_data.operations import (
    claim_next_job,
    execute_claimed_job,
    register_worker,
)


def main() -> int:
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    factory = make_session_factory(engine)
    summary: dict[str, object] = {}
    with TestClient(create_app(settings=settings, engine=engine)) as client:
        summary["liveness"] = client.get("/health/live").json()
        summary["readiness"] = client.get("/health/ready").json()
        providers = client.get("/api/v1/providers?page_size=100").json()["items"]
        stooq = next(item for item in providers if item["code"] == "stooq")
        summary["provider_status"] = client.get(f"/api/v1/providers/{stooq['id']}/status").json()
        payload = {
            "provider_code": "synthetic",
            "symbols": ["AAPL", "SPY"],
            "mode": "full",
            "start": "2026-07-06T00:00:00Z",
            "end": "2026-08-14T23:59:59Z",
        }
        created = client.post("/api/v1/import/jobs", json=payload)
        created.raise_for_status()
        job_id = created.json()["id"]
        with session_scope(factory) as session:
            worker = register_worker(session, "runtime-smoke-worker")
            claimed = claim_next_job(session, worker)
            if claimed is None:
                raise RuntimeError("runtime smoke could not claim the fixture import")
            job, lease = claimed
            execute_claimed_job(session, job, lease, worker)
        imported = client.get(f"/api/v1/import/jobs/{job_id}").json()
        if imported["status"] != "succeeded":
            raise RuntimeError("fixture import did not succeed")
        summary["fixture_import"] = {
            "status": imported["status"],
            "inserted": imported["records_inserted"],
        }
        with session_scope(factory) as session:
            provider = session.scalar(select(Provider).where(Provider.code == "synthetic"))
            if provider is None:
                raise RuntimeError("synthetic provider was not seeded")
            interrupted = ImportJob(
                provider_id=provider.id,
                mode="full",
                status="interrupted",
                symbols=["MSFT"],
                request_configuration={
                    "start": "2026-07-06T00:00:00+00:00",
                    "end": "2026-07-17T23:59:59+00:00",
                    "interval": "1d",
                },
                resume_cursor={},
            )
            session.add(interrupted)
            session.flush()
            interrupted_id = str(interrupted.id)
        restarted = client.post(f"/api/v1/import/jobs/{interrupted_id}/restart")
        restarted.raise_for_status()
        summary["restart"] = restarted.json()["status"]
        strategy_items = client.get("/api/v1/strategies?page_size=100").json()["items"]
        strategy_id = next(
            item["latest_version"]["id"]
            for item in strategy_items
            if item["strategy_type"] == "buy_and_hold"
        )
        backtest = client.post(
            "/api/v1/backtests",
            json={
                "strategy_version_id": strategy_id,
                "symbols": ["AAPL"],
                "benchmark_symbol": "SPY",
                "start_time": "2026-07-06T20:00:00Z",
                "end_time": "2026-08-14T20:00:00Z",
                "data_source_mode": "imported",
            },
        )
        backtest.raise_for_status()
        summary["backtest"] = backtest.json()["data_classification"]
        synthetic = next(item for item in providers if item["code"] == "synthetic")
        schedule = client.post(
            "/api/v1/import/schedules",
            json={
                "provider_id": synthetic["id"],
                "name": "runtime-smoke-schedule",
                "symbols": ["AAPL"],
                "next_run_at": datetime.now(UTC).isoformat(),
                "timezone": "UTC",
            },
        )
        schedule.raise_for_status()
        schedule_run = client.post(f"/api/v1/import/schedules/{schedule.json()['id']}/run-now")
        schedule_run.raise_for_status()
        with session_scope(factory) as session:
            worker = register_worker(session, "runtime-smoke-worker")
            claimed = claim_next_job(session, worker)
            if claimed is None:
                raise RuntimeError("runtime smoke could not claim the scheduled import")
            scheduled_job, lease = claimed
            execute_claimed_job(session, scheduled_job, lease, worker)
            summary["schedule"] = scheduled_job.status
        reconciliation = client.post("/api/v1/reconciliation/preview", json={"dry_run": True})
        reconciliation.raise_for_status()
        summary["reconciliation"] = {
            "records_checked": reconciliation.json()["records_checked"],
            "issues": reconciliation.json()["issue_count"],
        }
        summary["operations"] = client.get("/api/v1/operations/health").json()
    engine.dispose()
    print(json.dumps(summary, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
