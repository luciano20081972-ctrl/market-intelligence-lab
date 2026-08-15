from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta

from packages.core.config import get_settings
from packages.database.models import SchedulerHeartbeat
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.market_data.observability import configure_logging, operational_log
from packages.operations.service import claim_due_occurrences, recover_expired_occurrences

logger = logging.getLogger("operations.scheduler")


def parser() -> argparse.ArgumentParser:
    settings = get_settings()
    value = argparse.ArgumentParser(description="Run the durable private-beta scheduler")
    value.add_argument("--once", action="store_true")
    value.add_argument("--poll-interval", type=float, default=settings.scheduler_poll_interval)
    value.add_argument("--lease-seconds", type=int, default=settings.scheduler_lease_seconds)
    value.add_argument("--scheduler-id", default="")
    value.add_argument("--json-logs", action="store_true", default=settings.json_logs)
    return value


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    settings = get_settings()
    configure_logging(json_output=args.json_logs)
    factory = make_session_factory(create_database_engine(settings.database_url))
    identifier = (
        args.scheduler_id or f"{socket.gethostname()}:{os.getpid()}:{str(uuid.uuid4())[:8]}"
    )
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)
    with session_scope(factory) as session:
        heartbeat = SchedulerHeartbeat(
            scheduler_id=identifier,
            status="ONLINE",
            lease_expires_at=datetime.now(UTC) + timedelta(seconds=args.lease_seconds),
            version=settings.version,
            software_sha=settings.git_sha,
        )
        session.add(heartbeat)
        session.flush()
        heartbeat_id = heartbeat.id
    operational_log(logger, "scheduler_started", scheduler=identifier)
    try:
        while not stopping:
            with session_scope(factory) as session:
                current_heartbeat = session.get(SchedulerHeartbeat, heartbeat_id)
                if current_heartbeat is None:
                    raise RuntimeError("scheduler registration disappeared")
                now = datetime.now(UTC)
                current_heartbeat.last_heartbeat_at = now
                current_heartbeat.lease_expires_at = now + timedelta(seconds=args.lease_seconds)
                recovered = recover_expired_occurrences(session, now=now)
                claimed = claim_due_occurrences(
                    session,
                    identifier,
                    now=now,
                    lease_seconds=args.lease_seconds,
                )
                operational_log(
                    logger,
                    "scheduler_tick",
                    scheduler=identifier,
                    claimed=len(claimed),
                    recovered=len(recovered),
                )
            if args.once:
                break
            time.sleep(args.poll_interval)
    finally:
        with session_scope(factory) as session:
            current_heartbeat = session.get(SchedulerHeartbeat, heartbeat_id)
            if current_heartbeat is not None:
                current_heartbeat.status = "OFFLINE"
                current_heartbeat.last_heartbeat_at = datetime.now(UTC)
        operational_log(logger, "scheduler_stopped", scheduler=identifier)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
