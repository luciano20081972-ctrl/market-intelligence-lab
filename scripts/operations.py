from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import select

from packages.core.config import get_settings
from packages.database.models import Provider
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.market_data.ingestion import create_import_job, run_import_job
from packages.market_data.operations import process_due_schedules, queue_summary
from packages.market_data.reconciliation import preview_reconciliation, run_reconciliation
from packages.market_data.registry import default_registry


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Market-data operational utilities")
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("queue", help="show durable queue health")
    commands.add_parser("scheduler", help="enqueue schedules currently due")
    reconcile = commands.add_parser("reconcile", help="preview or persist reconciliation")
    reconcile.add_argument("--record", action="store_true")
    provider = commands.add_parser("provider-test", help="make one provider connectivity test")
    provider.add_argument("--provider", default="stooq")
    import_command = commands.add_parser("import", help="create a bounded one-shot import")
    import_command.add_argument("--provider", default="synthetic")
    import_command.add_argument("--symbols", required=True)
    import_command.add_argument("--start", required=True)
    import_command.add_argument("--end", required=True)
    import_command.add_argument("--run", action="store_true")
    import_command.add_argument("--dry-run", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    settings = get_settings()
    factory = make_session_factory(create_database_engine(settings.database_url))
    with session_scope(factory) as session:
        if args.command == "queue":
            result = queue_summary(session)
        elif args.command == "scheduler":
            jobs = process_due_schedules(session)
            result = {"created": len(jobs), "job_ids": [str(job.id) for job in jobs]}
        elif args.command == "reconcile":
            if args.record:
                run = run_reconciliation(session, dry_run=False)
                result = {"id": str(run.id), "issues": run.issue_count, "status": run.status}
            else:
                result = preview_reconciliation(session)
        elif args.command == "provider-test":
            provider = session.scalar(
                select(Provider).where(Provider.code == args.provider.lower())
            )
            if provider is None or not provider.is_enabled:
                raise ValueError("provider is unknown or disabled")
            adapter = default_registry.get(provider.code).adapter
            method = getattr(adapter, "test_connectivity", None)
            result = method() if method else adapter.health()
        else:
            start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
            end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
            job = create_import_job(
                session,
                provider_code=args.provider,
                symbols=args.symbols.split(","),
                mode="full",
                start=start,
                end=end,
                dry_run=args.dry_run,
            )
            if args.run:
                run_import_job(session, job)
            result = {"job_id": str(job.id), "status": job.status}
        print(json.dumps(result, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
