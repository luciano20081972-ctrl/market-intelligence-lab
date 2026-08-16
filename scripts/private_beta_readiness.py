from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from sqlalchemy import create_engine, text

from packages.core.config import EXPECTED_SCHEMA_REVISION, Settings, get_settings
from packages.database.phase5_reconciliation import inspect_phase5_reconciliation


def evaluate(settings: Settings, *, root: Path | None = None) -> dict[str, object]:
    base = (root or Path.cwd()).resolve()
    checks: dict[str, dict[str, str]] = {}
    reconciliation: dict[str, object] = {
        "status": "FAIL",
        "state": "DATABASE_UNAVAILABLE",
    }
    provider_rows: list[tuple[str, bool, str]] = []

    def check(name: str, passed: bool, message: str, *, warning: bool = False) -> None:
        checks[name] = {
            "status": "PASS" if passed else "WARN" if warning else "FAIL",
            "message": message,
        }

    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as connection:
            reconciliation = inspect_phase5_reconciliation(connection)
            provider_rows = [
                (str(row.code), bool(row.is_enabled), str(row.health))
                for row in connection.execute(text("SELECT code,is_enabled,health FROM providers"))
            ]
        reconciliation_state = str(reconciliation["state"])
        if reconciliation_state == "RECONCILED":
            check("DATABASE", True, "Database reconciled at the v0.14.1 head")
        elif reconciliation_state == "RECONCILIATION_REQUIRED":
            check(
                "DATABASE",
                False,
                "RECONCILIATION REQUIRED: recognized Phase-5 database; do not stamp",
                warning=True,
            )
        else:
            check("DATABASE", False, "Database migration history is not deployment-compatible")
    except Exception as exc:  # readiness must classify sanitized failures
        check("DATABASE", False, f"Database unavailable ({type(exc).__name__})")
    check(
        "AUTH",
        settings.auth_mode != "disabled",
        "Authentication is configured",
        warning=settings.environment != "production",
    )
    raw_path = (base / settings.raw_object_store_root).resolve()
    check(
        "STORAGE",
        raw_path.exists() and raw_path.is_dir(),
        "Persistent raw-object path is available",
    )
    usage = shutil.disk_usage(raw_path if raw_path.exists() else base)
    check("APPLICATION", True, f"Application version {settings.version}")
    check(
        "SECURITY",
        "*" not in settings.cors_origins and "*" not in settings.trusted_hosts,
        "Origins and hosts are bounded",
    )
    check(
        "SCHEDULER",
        settings.scheduler_enabled,
        "Durable scheduler is enabled",
        warning=not settings.scheduler_enabled,
    )
    check("WORKERS", settings.max_concurrent_ingestion_jobs > 0, "Worker budget is configured")
    required_providers = set(settings.required_live_providers)
    ready_providers = {
        code for code, enabled, health in provider_rows if enabled and health == "healthy"
    }
    unavailable_required = sorted(required_providers - ready_providers)
    check(
        "DATA",
        not unavailable_required,
        (
            "Required providers are healthy"
            if required_providers and not unavailable_required
            else f"Required providers unavailable: {', '.join(unavailable_required)}"
            if unavailable_required
            else "Optional providers may remain intentionally disabled or degraded"
        ),
    )
    check(
        "BACKUP",
        Path(base / settings.backup_root).exists(),
        "Backup path is configured",
        warning=True,
    )
    check("OBSERVABILITY", True, "Structured logs and internal metrics are available")
    check("PAPER_SAFETY", True, "Brokerage execution is not configured")
    check("DISK", usage.free >= settings.minimum_free_disk_bytes, "Free disk threshold satisfied")
    critical = {"APPLICATION", "DATABASE", "AUTH", "STORAGE", "SECURITY", "PAPER_SAFETY"}
    overall = (
        "FAIL"
        if any(checks[key]["status"] == "FAIL" for key in critical)
        else "WARN"
        if any(value["status"] == "WARN" for value in checks.values())
        else "PASS"
    )
    return {
        "status": overall,
        "version": settings.version,
        "schema_revision": EXPECTED_SCHEMA_REVISION,
        "reconciliation": reconciliation,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate private-beta deployment readiness")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(get_settings())
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(report["status"])
        report_checks = report["checks"]
        assert isinstance(report_checks, dict)
        for name, result in report_checks.items():
            assert isinstance(result, dict)
            print(f"{name}: {result['status']} - {result['message']}")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
