from __future__ import annotations

import argparse
import os
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.database.base import Base
from packages.database.models import ScheduledTaskDefinition, ScheduledTaskOccurrence
from packages.operations.service import claim_due_occurrences, recover_expired_occurrences


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark private-beta scheduler operations")
    parser.add_argument("--schedules", type=int, default=1_000)
    parser.add_argument("--occurrences", type=int, default=10_000)
    parser.add_argument("--database-url-env")
    args = parser.parse_args()
    database_url = os.environ.get(args.database_url_env, "") if args.database_url_env else ""
    engine = create_engine(database_url or "sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add_all(
            ScheduledTaskDefinition(
                name=f"benchmark-{index}",
                task_type="BENCHMARK",
                schedule_type="INTERVAL",
                schedule={"seconds": 3600},
                next_due_at=now,
                checksum=f"{index:064x}",
            )
            for index in range(args.schedules)
        )
        session.commit()
        began = time.perf_counter()
        claimed = claim_due_occurrences(session, "benchmark", now=now, limit=args.schedules)
        session.commit()
        claim_ms = (time.perf_counter() - began) * 1000
        definition_id = claimed[0].definition_id
        session.add_all(
            ScheduledTaskOccurrence(
                definition_id=definition_id,
                scheduled_for=now + timedelta(seconds=index + 1),
                idempotency_key=f"benchmark-occurrence-{index}",
                status="QUEUED",
            )
            for index in range(args.occurrences)
        )
        session.commit()
        began = time.perf_counter()
        depth = session.scalar(
            select(func.count(ScheduledTaskOccurrence.id)).where(
                ScheduledTaskOccurrence.status == "QUEUED"
            )
        )
        depth_ms = (time.perf_counter() - began) * 1000
        began = time.perf_counter()
        recover_expired_occurrences(session, now=now)
        recovery_ms = (time.perf_counter() - began) * 1000
    print(
        f"schedules={args.schedules} occurrences={depth} "
        f"claim_ms={claim_ms:.2f} queue_depth_ms={depth_ms:.2f} recovery_ms={recovery_ms:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
