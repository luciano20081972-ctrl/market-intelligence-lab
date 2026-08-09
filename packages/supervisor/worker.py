from __future__ import annotations

import argparse
import json
import os
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.compute.budget import BudgetLimits
from packages.compute.cloud_orchestration import reconcile_one_cloud_job, submit_one_cloud_job
from packages.compute.object_store import GoogleCloudStorageArtifactStore
from packages.compute.providers.cloud_run import (
    CloudRunConfiguration,
    GoogleCloudRunJobsProvider,
)
from packages.compute.providers.google_transport import GoogleAuthorizedHttpTransport
from packages.compute.resource_guard import LocalResourceGuard, ResourceSnapshot
from packages.compute.router import ComputeRouter, ProviderAvailability
from packages.compute.service import execute_one_local_job, reroute_one_held_job, running_local_jobs
from packages.core.config import Settings, get_settings
from packages.core.time import utc_now
from packages.database.models import MarketSupervisorHeartbeat
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.supervisor.market_session import market_session_state


def resource_guard(settings: Settings) -> LocalResourceGuard:
    return LocalResourceGuard(
        min_available_ram_mb=settings.local_min_available_ram_mb,
        max_load_per_cpu=settings.local_max_load_per_cpu,
        max_running_jobs=settings.local_max_analytical_jobs,
        heavy_concurrency=settings.local_heavy_concurrency,
        reserve_ram_mb=settings.local_reserved_ram_mb,
    )


def heartbeat(
    session: Session,
    settings: Settings,
    instance_id: str,
    *,
    last_error: str | None = None,
) -> MarketSupervisorHeartbeat:
    row = session.scalar(
        select(MarketSupervisorHeartbeat).where(
            MarketSupervisorHeartbeat.instance_id == instance_id
        )
    )
    if row is None:
        row = MarketSupervisorHeartbeat(instance_id=instance_id)
        session.add(row)
    snapshot = resource_guard(settings).snapshot()
    cloud_configured = bool(
        settings.cloud_project_id
        and settings.cloud_region
        and settings.cloud_run_job_name
        and settings.cloud_worker_image
        and settings.cloud_input_bucket
        and settings.cloud_result_bucket
        and settings.cloud_service_account
    )
    row.session_state = market_session_state().value
    row.cloud_enabled = settings.cloud_compute_enabled
    row.provider_health = {
        "local": "available",
        "cloud_run": (
            "disabled"
            if not settings.cloud_compute_enabled
            else "configured"
            if cloud_configured and not last_error
            else "unavailable"
            if last_error
            else "unconfigured"
        ),
        "google_batch": "future_provider",
    }
    row.scheduler_state = {
        "available_ram_mb": snapshot.available_ram_mb,
        "load_1m": snapshot.load_1m,
        "cpu_count": snapshot.cpu_count,
        "running_local_jobs": snapshot.running_analytical_jobs,
    }
    row.last_error = last_error
    row.heartbeat_at = utc_now()
    session.flush()
    return row


def health(session: Session, max_age_seconds: int = 120) -> dict[str, object]:
    row = session.scalar(
        select(MarketSupervisorHeartbeat).order_by(MarketSupervisorHeartbeat.heartbeat_at.desc())
    )
    current = datetime.now(UTC)
    healthy = bool(row and row.heartbeat_at >= current - timedelta(seconds=max_age_seconds))
    return {
        "status": "healthy" if healthy else "stale",
        "instance_id": row.instance_id if row else None,
        "heartbeat_at": row.heartbeat_at.isoformat() if row else None,
        "session_state": row.session_state if row else None,
        "cloud_enabled": row.cloud_enabled if row else False,
        "last_error": row.last_error if row else None,
    }


def cloud_provider(settings: Settings) -> GoogleCloudRunJobsProvider | None:
    required = (
        settings.cloud_project_id,
        settings.cloud_region,
        settings.cloud_run_job_name,
        settings.cloud_worker_image,
        settings.cloud_input_bucket,
        settings.cloud_result_bucket,
        settings.cloud_service_account,
    )
    if not settings.cloud_compute_enabled or not all(required):
        return None
    configuration = CloudRunConfiguration(
        project_id=settings.cloud_project_id or "",
        region=settings.cloud_region or "",
        job_name=settings.cloud_run_job_name or "",
        image=settings.cloud_worker_image or "",
        input_bucket=settings.cloud_input_bucket or "",
        result_bucket=settings.cloud_result_bucket or "",
        service_account=settings.cloud_service_account or "",
        max_parallel_tasks=settings.max_parallel_cloud_tasks,
    )
    return GoogleCloudRunJobsProvider(configuration, GoogleAuthorizedHttpTransport())


def budget_limits(settings: Settings) -> BudgetLimits:
    return BudgetLimits(
        cloud_enabled=settings.cloud_compute_enabled,
        max_job_usd=Decimal(str(settings.max_cloud_job_estimated_usd)),
        max_daily_usd=Decimal(str(settings.max_daily_cloud_compute_usd)),
        max_monthly_usd=Decimal(str(settings.max_monthly_cloud_compute_usd)),
        max_parallel_tasks=settings.max_parallel_cloud_tasks,
        max_runtime_seconds=settings.max_cloud_job_runtime,
        spend_cap_blocked=settings.cloud_spend_cap_blocked,
    )


def parser() -> argparse.ArgumentParser:
    settings = get_settings()
    value = argparse.ArgumentParser(description="Run the bounded market control-plane supervisor")
    value.add_argument("--once", action="store_true")
    value.add_argument("--health", action="store_true")
    value.add_argument("--poll-interval", type=float, default=settings.supervisor_poll_interval)
    value.add_argument("--instance-id", default="")
    return value


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.poll_interval < 1 or args.poll_interval > 300:
        raise ValueError("poll interval must be between 1 and 300 seconds")
    settings = get_settings()
    factory = make_session_factory(create_database_engine(settings.database_url))
    instance_id = args.instance_id or (
        f"{socket.gethostname()}:{os.getpid()}:{str(uuid.uuid4())[:8]}"
    )
    if args.health:
        with session_scope(factory) as session:
            result = health(session)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "healthy" else 1
    provider: GoogleCloudRunJobsProvider | None = None
    store: GoogleCloudStorageArtifactStore | None = None
    cloud_initialization_error: str | None = None
    try:
        provider = cloud_provider(settings)
        if provider is not None:
            store = GoogleCloudStorageArtifactStore()
    except Exception as exc:
        cloud_initialization_error = f"{type(exc).__name__}: {exc}"[:2000]
    while True:
        error: str | None = cloud_initialization_error
        try:
            with session_scope(factory) as session:
                guard = resource_guard(settings)
                live = guard.snapshot()
                reroute_one_held_job(
                    session,
                    router=ComputeRouter(guard),
                    snapshot=ResourceSnapshot(
                        live.available_ram_mb,
                        live.load_1m,
                        live.cpu_count,
                        running_local_jobs(session),
                    ),
                    limits=budget_limits(settings),
                    availability=ProviderAvailability(cloud_run=provider is not None),
                    include_cloud_holds=settings.cloud_compute_enabled,
                )
                execute_one_local_job(session, guard)
                if provider is not None and store is not None:
                    reconcile_one_cloud_job(
                        session,
                        provider,
                        store,
                        result_bucket=settings.cloud_result_bucket or "",
                    )
                    submit_one_cloud_job(
                        session,
                        provider,
                        store,
                        input_bucket=settings.cloud_input_bucket or "",
                    )
                heartbeat(session, settings, instance_id, last_error=error)
        except Exception as exc:  # supervisor must remain alive and expose its last failure
            error = f"{type(exc).__name__}: {exc}"[:2000]
            with session_scope(factory) as session:
                heartbeat(session, settings, instance_id, last_error=error)
        if args.once:
            return 1 if error else 0
        time.sleep(args.poll_interval)


if __name__ == "__main__":
    raise SystemExit(run())
