from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import Connection, inspect, text

LEGACY_REVISION = "3b2f6c7d8e90"
OFFICIAL_V014_REVISION = "5595df1fe1cf"
RECONCILIATION_REVISION = "a141c0de0001"
REAL_MARKET_FOUNDATION_REVISION = "f01500000001"

LEGACY_TABLES = {
    "compute_jobs",
    "compute_job_transitions",
    "cloud_usage_ledger",
    "market_supervisor_heartbeats",
    "data_freshness_observations",
    "decision_signals",
    "alert_events",
}

LEGACY_COLUMN_REQUIREMENTS = {
    "compute_jobs": {"id", "workspace_id", "requested_by_user_id", "submission_key", "state"},
    "compute_job_transitions": {"id", "job_id", "to_state", "created_at"},
    "cloud_usage_ledger": {"id", "workspace_id", "job_id", "provider"},
    "market_supervisor_heartbeats": {"id", "instance_id", "heartbeat_at"},
    "data_freshness_observations": {"id", "workspace_id", "source", "classification"},
    "decision_signals": {"id", "workspace_id", "symbol", "decision"},
    "alert_events": {"id", "workspace_id", "dedupe_key", "status"},
}

OFFICIAL_REVISIONS = {
    "eb1ff477509f",
    "e2517ff0412b",
    "4e398fc4c9a1",
    OFFICIAL_V014_REVISION,
}


def _count(connection: Connection, table: str) -> int:
    return int(connection.scalar(text(f'SELECT count(*) FROM "{table}"')) or 0)  # noqa: S608


def _orphan_count(connection: Connection, query: str) -> int:
    return int(connection.scalar(text(query)) or 0)


def inspect_phase5_reconciliation(connection: Connection) -> dict[str, Any]:
    """Inspect migration compatibility without changing database state."""
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if "alembic_version" not in tables:
        return {
            "status": "FAIL",
            "state": "UNVERSIONED",
            "current_revisions": [],
            "recognized_legacy_revision": False,
            "expected_legacy_tables_present": False,
            "model_schema_compatibility": False,
            "preservation_checks": {},
            "migration_path_available": True,
            "target_revision": RECONCILIATION_REVISION,
        }

    revisions = sorted(connection.scalars(text("SELECT version_num FROM alembic_version")))
    at_target = revisions in ([RECONCILIATION_REVISION], [REAL_MARKET_FOUNDATION_REVISION])
    legacy_revision = LEGACY_REVISION in revisions
    recognized = legacy_revision or at_target
    legacy_present = LEGACY_TABLES.issubset(tables)
    required_identity = {"user_profiles", "workspaces", "workspace_memberships"}
    identity_present = required_identity.issubset(tables)
    columns_ok = legacy_present and all(
        required.issubset({column["name"] for column in inspector.get_columns(table)})
        for table, required in LEGACY_COLUMN_REQUIREMENTS.items()
    )

    counts = {table: _count(connection, table) for table in sorted(LEGACY_TABLES & tables)}
    preservation: dict[str, Any] = {"row_counts": counts}
    if legacy_present and identity_present:
        preservation["orphan_compute_workspaces"] = _orphan_count(
            connection,
            "SELECT count(*) FROM compute_jobs c LEFT JOIN workspaces w "
            "ON w.id=c.workspace_id WHERE w.id IS NULL",
        )
        preservation["orphan_compute_users"] = _orphan_count(
            connection,
            "SELECT count(*) FROM compute_jobs c LEFT JOIN user_profiles u "
            "ON u.id=c.requested_by_user_id WHERE u.id IS NULL",
        )
        preservation["orphan_transitions"] = _orphan_count(
            connection,
            "SELECT count(*) FROM compute_job_transitions t LEFT JOIN compute_jobs j "
            "ON j.id=t.job_id WHERE j.id IS NULL",
        )
        identity_rows = connection.execute(
            text(
                "SELECT u.id, u.auth_subject, w.id, m.role "
                "FROM user_profiles u JOIN workspace_memberships m ON m.user_id=u.id "
                "JOIN workspaces w ON w.id=m.workspace_id ORDER BY u.id, w.id"
            )
        ).all()
        preservation["identity_linkage_checksum"] = hashlib.sha256(
            json.dumps([[str(value) for value in row] for row in identity_rows]).encode()
        ).hexdigest()
        preservation["identity_linkage_count"] = len(identity_rows)

    known_revisions = OFFICIAL_REVISIONS | {
        LEGACY_REVISION,
        RECONCILIATION_REVISION,
        REAL_MARKET_FOUNDATION_REVISION,
    }
    path_available = bool(revisions) and set(revisions).issubset(known_revisions)
    orphan_free = all(
        preservation.get(key, 0) == 0
        for key in ("orphan_compute_workspaces", "orphan_compute_users", "orphan_transitions")
    )
    compatible = identity_present and columns_ok and orphan_free
    if at_target and compatible:
        status, state = "PASS", "RECONCILED"
    elif legacy_revision and compatible and path_available:
        status, state = "WARN", "RECONCILIATION_REQUIRED"
    else:
        status, state = "FAIL", "INCOMPATIBLE"
    return {
        "status": status,
        "state": state,
        "current_revisions": revisions,
        "recognized_legacy_revision": recognized,
        "expected_legacy_tables_present": legacy_present,
        "model_schema_compatibility": compatible,
        "preservation_checks": preservation,
        "migration_path_available": path_available,
        "target_revision": RECONCILIATION_REVISION,
    }
