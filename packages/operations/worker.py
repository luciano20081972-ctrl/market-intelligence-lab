from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.database.models import ScheduledTaskDefinition, ScheduledTaskOccurrence
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.market_data.observability import configure_logging, operational_log
from packages.operations.service import (
    claim_next_occurrence,
    complete_occurrence,
    fail_occurrence,
    refresh_freshness,
)

logger = logging.getLogger("operations.worker")
Handler = Callable[[Session, ScheduledTaskDefinition], dict[str, Any]]


def _refresh_freshness(session: Session, _definition: ScheduledTaskDefinition) -> dict[str, Any]:
    return {"freshness_records_updated": refresh_freshness(session)}


HANDLERS: dict[str, Handler] = {
    "DATA_FRESHNESS": _refresh_freshness,
}


def execute_occurrence(session: Session, occurrence: ScheduledTaskOccurrence) -> None:
    definition = session.get(ScheduledTaskDefinition, occurrence.definition_id)
    if definition is None:
        fail_occurrence(
            session,
            occurrence,
            error_category="PERMANENT_VALIDATION",
            sanitized_error="Scheduled task definition no longer exists",
        )
        return
    handler = HANDLERS.get(definition.task_type)
    if handler is None:
        fail_occurrence(
            session,
            occurrence,
            error_category="AUTH_CONFIGURATION",
            sanitized_error="No approved handler is configured for this task type",
        )
        return
    occurrence.status = "RUNNING"
    try:
        complete_occurrence(session, occurrence, result_manifest=handler(session, definition))
    except (TimeoutError, ConnectionError) as exc:
        fail_occurrence(
            session,
            occurrence,
            error_category="TRANSIENT_NETWORK",
            sanitized_error=f"Task dependency failed ({type(exc).__name__})",
        )
    except (TypeError, ValueError) as exc:
        fail_occurrence(
            session,
            occurrence,
            error_category="PERMANENT_VALIDATION",
            sanitized_error=f"Task configuration failed ({type(exc).__name__})",
        )


def run(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run private-beta operational tasks")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=settings.worker_poll_interval)
    parser.add_argument("--worker-id", default="")
    parser.add_argument("--json-logs", action="store_true", default=settings.json_logs)
    args = parser.parse_args(argv)
    configure_logging(json_output=args.json_logs)
    identifier = args.worker_id or f"{socket.gethostname()}:{os.getpid()}:{str(uuid.uuid4())[:8]}"
    factory = make_session_factory(create_database_engine(settings.database_url))
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)
    while not stopping:
        processed = False
        with session_scope(factory) as session:
            occurrence = claim_next_occurrence(
                session,
                identifier,
                lease_seconds=settings.worker_lease_seconds,
            )
            if occurrence is not None:
                execute_occurrence(session, occurrence)
                processed = True
                operational_log(
                    logger,
                    "operational_task_finished",
                    worker=identifier,
                    occurrence_id=occurrence.id,
                    status=occurrence.status,
                )
        if args.once:
            break
        if not processed:
            time.sleep(args.poll_interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
