from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from packages.core.config import Settings
from packages.database.models import (
    LEGACY_WORKSPACE_ID,
    OperationalAlert,
    ProviderCircuitBreaker,
    ScheduledTaskDefinition,
    ScheduledTaskOccurrence,
)
from packages.database.session import make_session_factory, session_scope
from packages.market_data.observability import redact
from packages.operations.service import (
    admit_work,
    calculate_freshness,
    circuit_allows_request,
    claim_due_occurrences,
    claim_next_occurrence,
    compute_retry_delay,
    dependency_status,
    record_alert,
    record_provider_result,
    recover_expired_occurrences,
)
from packages.operations.worker import execute_occurrence
from packages.world_data.object_store import LocalRawObjectStore
from scripts.private_beta_backup import build_manifest


def _definition(now: datetime) -> ScheduledTaskDefinition:
    return ScheduledTaskDefinition(
        workspace_id=LEGACY_WORKSPACE_ID,
        name="Daily approved market refresh",
        task_type="MARKET_DATA_INGESTION",
        schedule_type="INTERVAL",
        schedule={"seconds": 3600},
        timezone="UTC",
        provider="fixture",
        next_due_at=now,
        checksum="a" * 64,
        retry_policy={"maximum_attempts": 3},
    )


def test_two_scheduler_instances_do_not_duplicate_occurrence(engine: Engine) -> None:
    factory = make_session_factory(engine)
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    with session_scope(factory) as session:
        session.add(_definition(now))
    with session_scope(factory) as session:
        assert len(claim_due_occurrences(session, "scheduler-a", now=now)) == 1
    with session_scope(factory) as session:
        assert claim_due_occurrences(session, "scheduler-b", now=now) == []
        assert session.scalar(select(func.count(ScheduledTaskOccurrence.id))) == 1


def test_operational_worker_completes_approved_task_and_quarantines_unknown(engine: Engine) -> None:
    factory = make_session_factory(engine)
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    with session_scope(factory) as session:
        approved = _definition(now)
        approved.task_type = "DATA_FRESHNESS"
        session.add(approved)
        session.flush()
        claim_due_occurrences(session, "scheduler", now=now)
        occurrence = claim_next_occurrence(session, "worker", now=now)
        assert occurrence is not None
        execute_occurrence(session, occurrence)
        assert occurrence.status == "SUCCEEDED"
        approved.enabled = False
        unknown = _definition(now + timedelta(hours=1))
        unknown.name = "Unknown task"
        unknown.task_type = "UNAPPROVED_TASK"
        session.add(unknown)
        session.flush()
        claim_due_occurrences(session, "scheduler", now=now + timedelta(hours=1))
        occurrence = claim_next_occurrence(session, "worker", now=now + timedelta(hours=1))
        assert occurrence is not None
        execute_occurrence(session, occurrence)
        assert occurrence.status == "QUARANTINED"
        assert occurrence.error_category == "AUTH_CONFIGURATION"


def test_expired_lease_is_reclaimable_then_quarantined(engine: Engine) -> None:
    factory = make_session_factory(engine)
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    with session_scope(factory) as session:
        definition = _definition(now)
        session.add(definition)
        session.flush()
        occurrence = ScheduledTaskOccurrence(
            definition_id=definition.id,
            workspace_id=LEGACY_WORKSPACE_ID,
            scheduled_for=now,
            idempotency_key="expired",
            status="RUNNING",
            claimed_by="lost-worker",
            lease_expires_at=now - timedelta(seconds=1),
            attempts=1,
        )
        session.add(occurrence)
        session.flush()
        recovered = recover_expired_occurrences(session, now=now)
        assert recovered[0].status == "RETRY_WAIT"
        assert recovered[0].next_retry_at and recovered[0].next_retry_at > now
        recovered[0].status = "RUNNING"
        recovered[0].attempts = 3
        recovered[0].lease_expires_at = now - timedelta(seconds=1)
        assert recover_expired_occurrences(session, now=now)[0].status == "QUARANTINED"


def test_retry_backoff_is_bounded_and_honors_retry_after() -> None:
    delays = [
        compute_retry_delay(attempt, jitter_seed="job").total_seconds() for attempt in range(1, 8)
    ]
    assert delays == sorted(delays)
    assert max(delays) <= 3600
    assert compute_retry_delay(1, retry_after_seconds=120).total_seconds() >= 120


def test_circuit_breaker_opens_and_allows_only_bounded_probe() -> None:
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    breaker = ProviderCircuitBreaker(provider_id=None)  # type: ignore[arg-type]
    for _ in range(3):
        record_provider_result(breaker, succeeded=False, now=now, error_category="RATE_LIMIT")
    assert breaker.state == "OPEN"
    assert not circuit_allows_request(breaker, now=now + timedelta(seconds=10))
    assert circuit_allows_request(breaker, now=now + timedelta(minutes=5))
    assert breaker.state == "HALF_OPEN"
    record_provider_result(breaker, succeeded=True, now=now + timedelta(minutes=5))
    assert breaker.state == "CLOSED"


def test_resource_budgets_defer_instead_of_overloading() -> None:
    decision = admit_work(active=2, backlog=4, maximum_active=2, maximum_backlog=10)
    assert decision == "DEFER_CONCURRENCY"
    assert admit_work(active=0, backlog=10, maximum_active=2, maximum_backlog=10) == "DEFER_BACKLOG"
    assert admit_work(active=0, backlog=0, maximum_active=2, maximum_backlog=10) == "ADMIT"


def test_market_calendar_freshness_does_not_mark_weekend_stale() -> None:
    friday = datetime(2026, 8, 14, 22, tzinfo=UTC)
    saturday = datetime(2026, 8, 15, 22, tzinfo=UTC)
    assert (
        calculate_freshness(
            now=saturday,
            last_success=friday,
            expected_next=friday + timedelta(hours=1),
            stale_after=friday + timedelta(hours=4),
            market_calendar=True,
        )
        == "CURRENT"
    )


def test_alerts_deduplicate_and_optional_provider_does_not_block_readiness(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        first = record_alert(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            severity="ERROR",
            category="STALE_CRITICAL_DATA",
            deduplication_key="dataset:fixture",
            summary="Fixture is stale",
        )
        second = record_alert(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            severity="ERROR",
            category="STALE_CRITICAL_DATA",
            deduplication_key="dataset:fixture",
            summary="Fixture remains stale",
        )
        assert first.id == second.id
        assert second.occurrence_count == 2
        assert session.scalar(select(func.count(OperationalAlert.id))) == 1
    assert dependency_status(database=True, required_storage=True, optional_provider=False) == {
        "status": "DEGRADED",
        "readiness": "ready",
        "optional_providers": "degraded",
    }


def test_production_configuration_fails_closed() -> None:
    common = {
        "environment": "production",
        "database_url": "postgresql://user:password@example.invalid/postgres",
        "auth_mode": "supabase",
        "supabase_url": "https://project.supabase.co",
        "supabase_project_ref": "project",
    }
    with pytest.raises(ValueError, match="Wildcard CORS"):
        Settings(**common, cors_origins=["*"])
    with pytest.raises(ValueError, match="forbidden in production"):
        Settings(**{**common, "auth_mode": "disabled"})


def test_secret_redaction_covers_headers_jwts_and_database_urls() -> None:
    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJvd25lciJ9.signature"
    message = (
        f"Authorization: Bearer {jwt} cookie=session-value "
        "postgresql://owner:top-secret@database.invalid/postgres"
    )
    safe = redact(message)
    assert "session-value" not in safe
    assert "top-secret" not in safe
    assert jwt not in safe


def test_operations_center_and_dependency_health_are_sanitized(client: TestClient) -> None:
    center = client.get("/api/v1/operations/center")
    assert center.status_code == 200
    assert set(center.json()["categories"]) == {
        "application",
        "database",
        "workers",
        "scheduler",
        "data",
        "authentication",
        "storage",
        "backups",
    }
    dependencies = client.get("/health/dependencies")
    assert dependencies.status_code == 200
    assert "database_url" not in dependencies.text.lower()
    manifest = client.get("/health/deployment").json()
    assert manifest["application_version"] == "0.14.1"
    assert manifest["alembic_revision"] == "a141c0de0001"


def test_backup_restore_fixture_round_trip_verifies_checksums(tmp_path: Path) -> None:
    source = LocalRawObjectStore(tmp_path / "source")
    key = "fixture/prices/2026/08/15/checksum"
    original = source.put(key, b"date,close\n2026-08-14,100\n", "text/csv")
    backup = tmp_path / "backup"
    shutil.copytree(tmp_path / "source", backup)
    restored = LocalRawObjectStore(tmp_path / "restored")
    shutil.copytree(backup, restored.root)
    assert restored.verify_checksum(key)
    assert restored.metadata(key).checksum == original.checksum
    manifest = build_manifest(
        database_reference="fixture/database.dump",
        object_reference="fixture/raw-objects",
        now=datetime(2026, 8, 15, 12, tzinfo=UTC),
    )
    assert len(str(manifest["checksum"])) == 64
    assert manifest["verification_state"] == "UNVERIFIED"
    assert manifest["configuration_template_version"] == "v0.14.1"
    assert manifest["compose_checksum"] == "capture-at-deployment"
    assert manifest["image_digests"] == []


def test_production_compose_has_only_reconciled_mil_topology() -> None:
    manifest = yaml.safe_load(Path("deploy/compose.production.yaml").read_text(encoding="utf-8"))
    services = manifest["services"]
    assert set(services) == {
        "api",
        "web",
        "market-data-worker",
        "scheduler",
        "operations-worker",
    }
    assert "supervisor" not in services
    assert "iamgodtranslator" not in str(manifest).lower()
    for service in services.values():
        assert service["restart"] == "unless-stopped"
        assert service["mem_limit"]
        assert service["cpus"]
        assert service["healthcheck"]
    assert services["scheduler"]["depends_on"]["api"]["condition"] == "service_healthy"
    assert services["operations-worker"]["depends_on"]["api"]["condition"] == (
        "service_healthy"
    )
