from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from packages.core.config import EXPECTED_SCHEMA_REVISION, get_settings


def build_manifest(
    *, database_reference: str, object_reference: str, now: datetime
) -> dict[str, object]:
    settings = get_settings()
    payload: dict[str, object] = {
        "database_backup_reference": database_reference,
        "object_store_reference": object_reference,
        "application_version": settings.version,
        "alembic_revision": EXPECTED_SCHEMA_REVISION,
        "configuration_template_version": "v0.14",
        "created_at": now.isoformat(),
        "status": "PLANNED",
        "verification_state": "UNVERIFIED",
    }
    payload["checksum"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a private-beta backup manifest")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument(
        "--apply", action="store_true", help="Reserved for an approved deployment run"
    )
    args = parser.parse_args()
    if args.apply:
        raise SystemExit(
            "Apply mode is deployment-specific; follow docs/operations/backup-and-restore.md"
        )
    now = datetime.now(UTC)
    root = args.output_root or Path(get_settings().backup_root)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    manifest = build_manifest(
        database_reference=f"{stamp}/database.dump",
        object_reference=f"{stamp}/raw-objects",
        now=now,
    )
    print(
        json.dumps(
            {"mode": "dry-run", "output": str(root / stamp), "manifest": manifest}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
