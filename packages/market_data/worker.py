from __future__ import annotations

import argparse
import logging
import os
import socket
import time
import uuid
from functools import partial

from packages.core.config import get_settings
from packages.database.models import WorkerInstance
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.market_data.observability import configure_logging, operational_log
from packages.market_data.operations import (
    claim_next_job,
    execute_claimed_job,
    process_due_schedules,
    queue_summary,
    recover_abandoned_jobs,
    register_worker,
    renew_lease,
    stop_worker,
)

logger = logging.getLogger("market_data.worker")


def parser() -> argparse.ArgumentParser:
    settings = get_settings()
    value = argparse.ArgumentParser(description="Run the Market Intelligence Lab import worker")
    value.add_argument("--once", action="store_true", help="process at most one job and exit")
    value.add_argument("--poll-interval", type=float, default=settings.worker_poll_interval)
    value.add_argument("--lease-seconds", type=int, default=settings.worker_lease_seconds)
    value.add_argument("--json-logs", action="store_true", default=settings.json_logs)
    value.add_argument("--health", action="store_true", help="print queue health and exit")
    value.add_argument("--worker-id", default="")
    return value


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.poll_interval < 0.1 or args.poll_interval > 300:
        raise ValueError("poll interval must be between 0.1 and 300 seconds")
    if args.lease_seconds < 10 or args.lease_seconds > 3600:
        raise ValueError("lease seconds must be between 10 and 3600")
    configure_logging(json_output=args.json_logs)
    settings = get_settings()
    factory = make_session_factory(create_database_engine(settings.database_url))
    identifier = args.worker_id or (f"{socket.gethostname()}:{os.getpid()}:{str(uuid.uuid4())[:8]}")
    if args.health:
        with session_scope(factory) as session:
            operational_log(logger, "worker_health", worker=identifier, **queue_summary(session))
        return 0
    with session_scope(factory) as session:
        worker = register_worker(session, identifier, {"mode": "once" if args.once else "poll"})
        worker_id = worker.id
    operational_log(logger, "worker_started", worker=identifier)
    try:
        while True:
            processed = False
            with session_scope(factory) as session:
                current_worker = session.get(WorkerInstance, worker_id)
                if current_worker is None:
                    raise RuntimeError("worker registration disappeared")
                recover_abandoned_jobs(session)
                process_due_schedules(session)
                claimed = claim_next_job(session, current_worker, lease_seconds=args.lease_seconds)
                if claimed:
                    job, lease = claimed
                    execute_claimed_job(
                        session,
                        job,
                        lease,
                        current_worker,
                        heartbeat=partial(
                            renew_lease,
                            session,
                            lease,
                            current_worker,
                            lease_seconds=args.lease_seconds,
                        ),
                    )
                    processed = True
                    operational_log(
                        logger,
                        "job_finished",
                        worker=identifier,
                        job_id=job.id,
                        provider_id=job.provider_id,
                        status=job.status,
                        processed=job.records_processed,
                        accepted=job.records_inserted,
                        rejected=job.records_skipped,
                        retries=max(job.attempt - 1, 0),
                        duration_ms=job.processing_duration_ms,
                    )
            if args.once:
                return 0
            if not processed:
                time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        operational_log(logger, "worker_shutdown_requested", worker=identifier)
        return 0
    finally:
        with session_scope(factory) as session:
            current = session.get(WorkerInstance, worker_id)
            if current is not None:
                stop_worker(session, current)


if __name__ == "__main__":
    raise SystemExit(run())
