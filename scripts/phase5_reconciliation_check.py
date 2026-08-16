from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.core.config import get_settings
from packages.database.phase5_reconciliation import (
    RECONCILIATION_REVISION,
    inspect_phase5_reconciliation,
)
from packages.database.session import create_database_engine


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Phase-5 to v0.14.1 database compatibility check"
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-head", action="store_true")
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--compare-snapshot", type=Path)
    args = parser.parse_args()
    try:
        engine = create_database_engine(get_settings().database_url)
        try:
            with engine.connect() as connection:
                report = inspect_phase5_reconciliation(connection)
        finally:
            engine.dispose()
    except Exception as exc:
        report = {
            "status": "FAIL",
            "state": "DATABASE_UNAVAILABLE",
            "current_revisions": [],
            "recognized_legacy_revision": False,
            "expected_legacy_tables_present": False,
            "model_schema_compatibility": False,
            "preservation_checks": {"error_class": type(exc).__name__},
            "migration_path_available": False,
            "target_revision": RECONCILIATION_REVISION,
        }
    if args.require_head and report["state"] != "RECONCILED":
        report["status"] = "FAIL"
    if args.snapshot_output:
        args.snapshot_output.write_text(
            json.dumps(report["preservation_checks"], sort_keys=True), encoding="utf-8"
        )
    if args.compare_snapshot:
        expected = json.loads(args.compare_snapshot.read_text(encoding="utf-8"))
        matched = expected == report["preservation_checks"]
        report["preservation_snapshot_match"] = matched
        if not matched:
            report["status"] = "FAIL"
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        for label, key in (
            ("STATUS", "status"),
            ("STATE", "state"),
            ("CURRENT REVISION", "current_revisions"),
            ("RECOGNIZED LEGACY REVISION", "recognized_legacy_revision"),
            ("EXPECTED LEGACY TABLES PRESENT", "expected_legacy_tables_present"),
            ("MODEL/SCHEMA COMPATIBILITY", "model_schema_compatibility"),
            ("PRESERVATION CHECKS", "preservation_checks"),
            ("MIGRATION PATH AVAILABLE", "migration_path_available"),
            ("TARGET REVISION", "target_revision"),
        ):
            print(f"{label}: {report[key]}")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
