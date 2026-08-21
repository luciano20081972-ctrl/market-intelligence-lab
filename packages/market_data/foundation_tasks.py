from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import (
    LEGACY_WORKSPACE_ID,
    Asset,
    AssetListing,
    Provider,
    ScheduledTaskDefinition,
)
from packages.market_data.ingestion import create_import_job
from packages.market_data.operating_modes import determine_operating_mode
from packages.market_data.real_providers import AlpacaBasicAdapter
from packages.market_data.reference_sources import (
    NasdaqReferenceAdapter,
    SecCompanyTickerAdapter,
    reconcile_reference_records,
)
from packages.market_data.universe import select_dynamic_universe


def _network_enabled(definition: ScheduledTaskDefinition) -> bool:
    return bool(
        definition.configuration.get("network_enabled", False)
        or os.getenv("MIL_REFERENCE_NETWORK_ENABLED", "").lower() in {"1", "true", "yes"}
    )


def refresh_reference_universe(
    session: Session, definition: ScheduledTaskDefinition
) -> dict[str, Any]:
    if not _network_enabled(definition):
        return {
            "status": "NOT_CONFIGURED",
            "catalog_preserved": True,
            "message": "Official reference refresh is installed but network opt-in is disabled",
        }
    records = NasdaqReferenceAdapter().fetch()
    records.extend(SecCompanyTickerAdapter().fetch())
    result = reconcile_reference_records(session, records)
    return {"status": "SUCCEEDED", **result}


def refresh_operating_mode(
    session: Session, _definition: ScheduledTaskDefinition
) -> dict[str, Any]:
    state = determine_operating_mode(session)
    return {
        "status": "SUCCEEDED",
        "mode": state.mode,
        "next_transition_at": (
            state.next_transition_at.isoformat() if state.next_transition_at else None
        ),
    }


def refresh_dynamic_universe(
    session: Session, definition: ScheduledTaskDefinition
) -> dict[str, Any]:
    capacity = int(
        definition.configuration.get(
            "realtime_capacity", os.getenv("MIL_ALPACA_REALTIME_CAPACITY", "30")
        )
    )
    run = select_dynamic_universe(
        session,
        workspace_id=definition.workspace_id,
        realtime_capacity=capacity,
        candidate_capacity=int(definition.configuration.get("candidate_capacity", 100)),
        active_capacity=int(definition.configuration.get("active_capacity", 200)),
    )
    return {
        "status": run.status,
        "eligible": run.input_asset_count,
        "candidates": run.candidate_count,
        "active": run.active_count,
        "realtime": run.realtime_count,
    }


def schedule_historical_ingestion(
    session: Session, definition: ScheduledTaskDefinition
) -> dict[str, Any]:
    provider_code = str(definition.provider or "massive")
    provider = session.scalar(select(Provider).where(Provider.code == provider_code))
    if provider is None or not provider.is_enabled:
        return {
            "status": "PROVIDER_UNAVAILABLE",
            "provider": provider_code,
            "catalog_preserved": True,
        }
    limit = min(max(int(definition.configuration.get("batch_symbols", 25)), 1), 100)
    assets = session.scalars(
        select(Asset)
        .join(AssetListing, AssetListing.asset_id == Asset.id)
        .where(
            Asset.is_active.is_(True),
            AssetListing.eligibility_status == "ELIGIBLE",
            AssetListing.is_active.is_(True),
        )
        .order_by(Asset.symbol)
        .limit(limit)
    ).unique().all()
    if not assets:
        return {"status": "NO_ELIGIBLE_ASSETS", "queued": 0}
    end = datetime.now(UTC)
    start = end - timedelta(days=int(definition.configuration.get("lookback_days", 730)))
    day_key = end.date().isoformat()
    job = create_import_job(
        session,
        provider_code=provider_code,
        symbols=[asset.symbol for asset in assets],
        mode="incremental",
        start=start,
        end=end,
        adjustment_preference="provider_default",
        idempotency_key=f"v015:{provider_code}:{day_key}:priority-5",
        queue_name="automatic-market-data",
        workspace_id=definition.workspace_id,
        priority=500,
        resource_class="IO_HEAVY",
    )
    return {"status": "QUEUED", "job_id": str(job.id), "symbols": len(job.symbols)}


def scheduled_task_specs(now: datetime) -> tuple[dict[str, Any], ...]:
    return (
        {
            "name": "Official U.S. security-master refresh",
            "task_type": "REFERENCE_UNIVERSE_REFRESH",
            "schedule_type": "DAILY",
            "schedule": {"hour_utc": 5},
            "provider": "nasdaq_trader+sec",
            "configuration": {"network_enabled": False},
            "next_due_at": now,
            "maximum_runtime_seconds": 900,
            "resource_budget": {"class": "IO_STANDARD", "maximum_memory_mb": 256},
        },
        {
            "name": "Real-market historical ingestion",
            "task_type": "HISTORICAL_BACKFILL",
            "schedule_type": "MARKET_CALENDAR",
            "schedule": {"days": 1},
            "provider": "massive",
            "configuration": {"batch_symbols": 25, "lookback_days": 730},
            "next_due_at": now,
            "maximum_runtime_seconds": 3600,
            "resource_budget": {"class": "IO_HEAVY", "maximum_memory_mb": 512},
        },
        {
            "name": "Dynamic market universe selection",
            "task_type": "DYNAMIC_UNIVERSE",
            "schedule_type": "INTERVAL",
            "schedule": {"seconds": 900},
            "provider": "alpaca",
            "configuration": {
                "realtime_capacity": AlpacaBasicAdapter().realtime_capacity,
                "candidate_capacity": 100,
                "active_capacity": 200,
            },
            "next_due_at": now,
            "maximum_runtime_seconds": 300,
            "resource_budget": {"class": "CPU_LIGHT", "maximum_memory_mb": 384},
        },
        {
            "name": "Exchange-calendar operating mode",
            "task_type": "MARKET_OPERATING_MODE",
            "schedule_type": "INTERVAL",
            "schedule": {"seconds": 300},
            "provider": None,
            "configuration": {"calendar": "XNYS"},
            "next_due_at": now,
            "maximum_runtime_seconds": 60,
            "resource_budget": {"class": "CPU_LIGHT", "maximum_memory_mb": 128},
        },
    )


def seed_foundation_tasks(session: Session, *, now: datetime) -> int:
    inserted = 0
    for spec in scheduled_task_specs(now):
        existing = session.scalar(
            select(ScheduledTaskDefinition).where(
                ScheduledTaskDefinition.workspace_id == LEGACY_WORKSPACE_ID,
                ScheduledTaskDefinition.task_type == spec["task_type"],
                ScheduledTaskDefinition.name == spec["name"],
            )
        )
        payload = json.dumps(spec, sort_keys=True, default=str, separators=(",", ":"))
        checksum = hashlib.sha256(payload.encode()).hexdigest()
        if existing is None:
            session.add(
                ScheduledTaskDefinition(
                    workspace_id=LEGACY_WORKSPACE_ID,
                    enabled=True,
                    timezone="UTC",
                    policy_version="v0.15.0",
                    retry_policy={"maximum_attempts": 5, "exponential_backoff": True},
                    concurrency_policy={"maximum_active": 1, "defer_during_market": False},
                    checksum=checksum,
                    **spec,
                )
            )
            inserted += 1
        else:
            existing.schedule = spec["schedule"]
            existing.configuration = spec["configuration"]
            existing.resource_budget = spec["resource_budget"]
            existing.checksum = checksum
    return inserted
