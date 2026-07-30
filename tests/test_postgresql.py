from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from packages.database.models import (
    LEGACY_WORKSPACE_ID,
    ImportJob,
    JobLease,
    PriceBar,
    Watchlist,
)
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.market_data.ingestion import create_import_job
from packages.market_data.operations import claim_next_job, register_worker
from packages.market_data.seed import seed_demonstration_data

pytestmark = pytest.mark.postgres


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
        assert (
            session.scalar(
                select(func.count(JobLease.id)).where(JobLease.job_id == job_id)
            )
            == 1
        )


def test_postgres_session_context_does_not_leak(postgres_factory) -> None:  # type: ignore[no-untyped-def]
    first = postgres_factory()
    first.info["workspace_id"] = LEGACY_WORKSPACE_ID
    first.close()
    second = postgres_factory()
    try:
        assert "workspace_id" not in second.info
    finally:
        second.close()
