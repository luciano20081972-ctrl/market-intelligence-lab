from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from packages.database.models import (
    LEGACY_WORKSPACE_ID,
    EconomicEntity,
    FactorExperiment,
    ImportJob,
    JobLease,
    PriceBar,
    ResearchHypothesis,
    UserProfile,
    Watchlist,
    Workspace,
    WorkspaceMembership,
)
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.economic_graph.fixtures import FIXTURE_TIME
from packages.economic_graph.traversal import postgres_recursive_neighborhood
from packages.hypothesis.fixtures import seed_reference_hypothesis_research
from packages.hypothesis.service import claim_factor_experiment
from packages.market_data.ingestion import create_import_job
from packages.market_data.operations import (
    claim_next_job,
    recover_abandoned_jobs,
    register_worker,
)
from packages.market_data.seed import seed_demonstration_data
from packages.security.tenant import install_workspace_guards

pytestmark = pytest.mark.postgres
install_workspace_guards()


@pytest.fixture(scope="module")
def postgres_factory():  # type: ignore[no-untyped-def]
    url = os.getenv("MIL_POSTGRES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MIL_POSTGRES_TEST_DATABASE_URL is not configured")
    engine = create_database_engine(url)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        seed_demonstration_data(
            session, calendar_start=date(2025, 1, 1), calendar_end=date(2027, 12, 31)
        )
    yield factory
    engine.dispose()


def test_postgres_uuid_decimal_and_timezone_round_trip(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    with session_scope(postgres_factory) as session:
        bar = session.scalar(select(PriceBar).order_by(PriceBar.event_time))
        assert bar is not None
        assert isinstance(bar.id, uuid.UUID)
        assert isinstance(bar.close, Decimal)
        assert bar.event_time.tzinfo is not None


def test_postgres_transaction_rollback(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    name = f"rollback-{uuid.uuid4()}"
    with pytest.raises(RuntimeError):
        with session_scope(postgres_factory) as session:
            session.add(Watchlist(workspace_id=LEGACY_WORKSPACE_ID, name=name))
            raise RuntimeError("force rollback")
    with session_scope(postgres_factory) as session:
        assert session.scalar(select(Watchlist).where(Watchlist.name == name)) is None


def test_postgres_workspace_unique_constraint(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    name = f"unique-{uuid.uuid4()}"
    with session_scope(postgres_factory) as session:
        session.add_all(
            [
                Watchlist(workspace_id=LEGACY_WORKSPACE_ID, name=name),
                Watchlist(workspace_id=LEGACY_WORKSPACE_ID, name=name),
            ]
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_postgres_concurrent_claim_is_single_winner(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    with session_scope(postgres_factory) as session:
        job = create_import_job(
            session,
            provider_code="synthetic",
            symbols=["AAPL"],
            mode="incremental",
            start=datetime(2026, 7, 1, tzinfo=UTC),
            end=datetime(2026, 7, 2, tzinfo=UTC),
            idempotency_key=f"postgres-concurrency-{uuid.uuid4()}",
            workspace_id=LEGACY_WORKSPACE_ID,
        )
        job_id = job.id

    def claim(identifier: str) -> str | None:
        with session_scope(postgres_factory) as session:
            worker = register_worker(session, identifier)
            claimed = claim_next_job(session, worker)
            return str(claimed[0].id) if claimed else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, [f"worker-{uuid.uuid4()}", f"worker-{uuid.uuid4()}"]))
    assert results.count(str(job_id)) == 1
    with session_scope(postgres_factory) as session:
        assert session.scalar(select(ImportJob.status).where(ImportJob.id == job_id)) == "running"
        assert session.scalar(select(func.count(JobLease.id)).where(JobLease.job_id == job_id)) == 1


def test_postgres_session_context_does_not_leak(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    first = postgres_factory()
    first.info["workspace_id"] = LEGACY_WORKSPACE_ID
    first.close()
    second = postgres_factory()
    try:
        assert "workspace_id" not in second.info
    finally:
        second.close()


def test_postgres_rls_is_enabled_without_workspace_policies(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    with session_scope(postgres_factory) as session:
        enabled = session.execute(
            select(func.count()).select_from(
                text(
                    "pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "AND n.nspname='public' AND c.relrowsecurity"
                )
            )
        ).scalar_one()
        policies = session.scalar(
            select(func.count()).select_from(text("pg_policies")).where(text("schemaname='public'"))
        )
    assert enabled >= 47
    assert policies == 0


def test_postgres_workspace_loader_and_write_guards(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    with session_scope(postgres_factory) as session:
        session.info["bypass_workspace_scope"] = True
        session.add(
            UserProfile(
                id=user_id,
                auth_subject=f"postgres-{user_id}",
                email=f"{user_id}@example.test",
            )
        )
        session.flush()
        session.add(
            Workspace(
                id=workspace_id,
                name="PostgreSQL Workspace B",
                slug=f"postgres-{workspace_id}",
                created_by_user_id=user_id,
            )
        )
        session.flush()
        session.add(WorkspaceMembership(workspace_id=workspace_id, user_id=user_id, role="viewer"))
        session.add(Watchlist(workspace_id=workspace_id, name=f"private-{uuid.uuid4()}"))
    with session_scope(postgres_factory) as session:
        session.info["workspace_id"] = LEGACY_WORKSPACE_ID
        assert (
            session.scalar(select(Watchlist).where(Watchlist.workspace_id == workspace_id)) is None
        )
        session.add(Watchlist(workspace_id=workspace_id, name=f"blocked-{uuid.uuid4()}"))
        with pytest.raises(PermissionError, match="Cross-workspace write"):
            session.flush()
        session.rollback()


def test_postgres_expired_lease_recovery(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    current = datetime.now(UTC)
    with session_scope(postgres_factory) as session:
        job = create_import_job(
            session,
            provider_code="synthetic",
            symbols=["AAPL"],
            mode="incremental",
            start=current,
            end=current + timedelta(days=1),
            idempotency_key=f"postgres-recovery-{uuid.uuid4()}",
            workspace_id=LEGACY_WORKSPACE_ID,
        )
        worker = register_worker(session, f"recovery-{uuid.uuid4()}")
        claimed = claim_next_job(
            session, worker, lease_seconds=10, now=current - timedelta(minutes=1)
        )
        assert claimed is not None and claimed[0].id == job.id
    with session_scope(postgres_factory) as session:
        assert recover_abandoned_jobs(session, now=current) == [job.id]
        assert session.scalar(select(ImportJob.status).where(ImportJob.id == job.id)) == "retrying"
        assert session.scalar(select(func.count(JobLease.id)).where(JobLease.job_id == job.id)) == 0


def test_postgres_graph_constraints_and_temporal_types(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    with session_scope(postgres_factory) as session:
        company = session.scalar(
            select(EconomicEntity).where(EconomicEntity.canonical_name == "Silica Systems")
        )
        assert company is not None
        assert company.simulation_eligible_time.tzinfo is not None
        company.confidence = Decimal("1.1")
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_postgres_recursive_graph_and_as_of_boundary(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    with session_scope(postgres_factory) as session:
        company = session.scalar(
            select(EconomicEntity).where(EconomicEntity.canonical_name == "Silica Systems")
        )
        assert company is not None
        before = postgres_recursive_neighborhood(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            start_entity_id=company.id,
            as_of=FIXTURE_TIME - timedelta(seconds=1),
            max_depth=3,
            max_nodes=100,
        )
        visible = postgres_recursive_neighborhood(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            start_entity_id=company.id,
            as_of=FIXTURE_TIME,
            max_depth=3,
            max_nodes=100,
        )
        assert len(before) == 1
        assert len(visible) > 1
        assert max(row["depth"] for row in visible) <= 3


def test_postgres_graph_query_indexes_exist(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    expected = {
        "ix_economic_entity_workspace_eligible",
        "ix_economic_relationship_outbound",
        "ix_economic_relationship_inbound",
        "ix_entity_identifier_entity_namespace",
        "ix_data_relevance_company_created",
    }
    with session_scope(postgres_factory) as session:
        found = set(
            session.scalars(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname='public' AND indexname = ANY(:names)"
                ).bindparams(names=list(expected))
            )
        )
    assert found == expected


def test_postgres_hypothesis_schema_constraints_and_indexes(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    with session_scope(postgres_factory) as session:
        seed_reference_hypothesis_research(session, LEGACY_WORKSPACE_ID)
        session.commit()
        expected = {
            "ix_hypothesis_subject_status",
            "ix_factor_experiment_hypothesis_status",
            "ix_factor_fold_experiment_ranges",
        }
        found = set(
            session.scalars(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname='public' AND indexname = ANY(:names)"
                ).bindparams(names=list(expected))
            )
        )
        assert found == expected
        hypothesis = session.scalar(select(ResearchHypothesis))
        assert hypothesis is not None
        hypothesis.status = "INVALID"
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_postgres_factor_experiment_claim_has_one_winner(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    with session_scope(postgres_factory) as session:
        seed_reference_hypothesis_research(session, LEGACY_WORKSPACE_ID)
        original = session.scalar(select(FactorExperiment))
        assert original is not None
        queued = FactorExperiment(
            workspace_id=original.workspace_id,
            hypothesis_id=original.hypothesis_id,
            candidate_feature_spec_id=original.candidate_feature_spec_id,
            universe_version_id=original.universe_version_id,
            feature_snapshot_id=original.feature_snapshot_id,
            outcome_definition_id=original.outcome_definition_id,
            graph_state=original.graph_state,
            period_start=original.period_start,
            period_end=original.period_end,
            validation_protocol=original.validation_protocol,
            cost_assumptions=original.cost_assumptions,
            application_sha=original.application_sha,
            dependency_versions=original.dependency_versions,
            seed=original.seed + 99,
            status="SCHEDULED",
            checksum=f"postgres-claim-{uuid.uuid4()}".replace("-", "")[:64],
        )
        session.add(queued)
        session.flush()
        queued_id = queued.id

    def claim() -> str | None:
        with session_scope(postgres_factory) as session:
            item = claim_factor_experiment(session)
            return str(item.id) if item else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: claim(), range(2)))
    assert results.count(str(queued_id)) == 1
    with session_scope(postgres_factory) as session:
        status = session.scalar(
            select(FactorExperiment.status).where(FactorExperiment.id == queued_id)
        )
        assert status == "RUNNING"


def test_postgres_completed_factor_experiment_is_immutable(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    with session_scope(postgres_factory) as session:
        seed_reference_hypothesis_research(session, LEGACY_WORKSPACE_ID)
        experiment = session.scalar(
            select(FactorExperiment).where(FactorExperiment.status == "COMPLETED")
        )
        assert experiment is not None
        experiment.seed += 1
        with pytest.raises(ValueError, match="immutable"):
            session.flush()
        session.rollback()
