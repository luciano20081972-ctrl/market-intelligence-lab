from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import create_engine, inspect, text

from packages.core.config import EXPECTED_SCHEMA_REVISION
from packages.database.phase5_reconciliation import (
    LEGACY_TABLES,
    inspect_phase5_reconciliation,
)
from scripts.seed_phase5_reconciliation_fixture import JOB_ID, USER_ID, WORKSPACE_ID

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def reconciliation_connection():  # type: ignore[no-untyped-def]
    url = os.getenv("MIL_POSTGRES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MIL_POSTGRES_TEST_DATABASE_URL is not configured")
    engine = create_engine(url)
    with engine.connect() as connection:
        yield connection
    engine.dispose()


def test_reconciliation_has_one_head_and_preserves_legacy_schema(
    reconciliation_connection,
) -> None:  # type: ignore[no-untyped-def]
    report = inspect_phase5_reconciliation(reconciliation_connection)
    assert report["status"] == "PASS"
    assert report["current_revisions"] == [EXPECTED_SCHEMA_REVISION]
    assert report["expected_legacy_tables_present"] is True
    assert LEGACY_TABLES.issubset(set(inspect(reconciliation_connection).get_table_names()))


def test_phase5_fixture_data_and_owner_linkage_survive(
    reconciliation_connection,
) -> None:  # type: ignore[no-untyped-def]
    if os.getenv("MIL_PHASE5_FIXTURE_EXPECTED") != "true":
        pytest.skip("exact Phase-5 fixture is exercised by PostgreSQL 18 reconciliation CI")
    profile = reconciliation_connection.execute(
        text("SELECT id,auth_subject FROM user_profiles WHERE id=:id"), {"id": USER_ID}
    ).one()
    workspace = reconciliation_connection.execute(
        text("SELECT id,created_by_user_id FROM workspaces WHERE id=:id"), {"id": WORKSPACE_ID}
    ).one()
    membership = reconciliation_connection.execute(
        text(
            "SELECT role FROM workspace_memberships "
            "WHERE workspace_id=:workspace_id AND user_id=:user_id"
        ),
        {"workspace_id": WORKSPACE_ID, "user_id": USER_ID},
    ).one()
    job = reconciliation_connection.execute(
        text("SELECT id,workspace_id,requested_by_user_id,state FROM compute_jobs WHERE id=:id"),
        {"id": JOB_ID},
    ).one()
    assert UUID(str(profile.id)) == USER_ID
    assert profile.auth_subject == "fixture-supabase-owner-subject"
    assert UUID(str(workspace.id)) == WORKSPACE_ID
    assert UUID(str(workspace.created_by_user_id)) == USER_ID
    assert membership.role == "owner"
    assert UUID(str(job.workspace_id)) == WORKSPACE_ID
    assert UUID(str(job.requested_by_user_id)) == USER_ID
    assert job.state == "SUCCEEDED"
    report = inspect_phase5_reconciliation(reconciliation_connection)
    checks = report["preservation_checks"]
    assert checks["identity_linkage_count"] >= 1
    assert checks["orphan_compute_workspaces"] == 0
    assert checks["orphan_compute_users"] == 0
    assert checks["orphan_transitions"] == 0
    assert all(checks["row_counts"][table] >= 1 for table in LEGACY_TABLES)
