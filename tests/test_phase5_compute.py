from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from packages.compute.budget import BudgetLimits, BudgetUsage, evaluate_budget
from packages.compute.cloud_worker import execute_partition
from packages.compute.manifests import canonical_checksum, validate_result_manifest
from packages.compute.providers.cloud_run import (
    CloudRunConfiguration,
    GoogleCloudRunJobsProvider,
)
from packages.compute.providers.local import LocalComputeProvider
from packages.compute.resource_guard import LocalResourceGuard, ResourceSnapshot
from packages.compute.router import ComputeRouter, ProviderAvailability
from packages.compute.service import cancel_job, retry_job
from packages.compute.sharding import deterministic_merge, deterministic_shards
from packages.compute.types import (
    ComputeJobSpec,
    ComputeProviderName,
    ComputeState,
    JobClass,
    ResourceEstimate,
)
from packages.database.models import LEGACY_USER_ID, LEGACY_WORKSPACE_ID, ComputeJob
from packages.database.session import make_session_factory, session_scope
from packages.supervisor.alerts import AlertCandidate, InAppAlertChannel
from packages.supervisor.freshness import FreshnessClassification, classify_freshness
from packages.supervisor.market_session import MarketSessionState, market_session_state
from packages.supervisor.safety import assert_research_or_paper_only
from packages.supervisor.signals import Decision, SignalCandidate, evaluate_signal


def spec(job_class: JobClass = JobClass.INTERACTIVE_LIGHT, *, cost: str = "0") -> ComputeJobSpec:
    return ComputeJobSpec(
        workspace_id=LEGACY_WORKSPACE_ID,
        requested_by=LEGACY_USER_ID,
        submission_key="phase5-unit",
        job_type="deterministic_fixture",
        job_class=job_class,
        estimate=ResourceEstimate(Decimal("1"), 256, 30, Decimal(cost)),
        input_manifest={"fixture": True},
        input_manifest_hash="a" * 64,
        model_version="fixture-v1",
    )


def test_compute_provider_contract_and_local_idempotency() -> None:
    calls: list[UUID] = []
    provider = LocalComputeProvider(lambda value: calls.append(value.job_id) or {})
    first = provider.submit(spec())
    second = provider.submit(spec())
    assert provider.health().available
    assert provider.estimate_cost(spec()) == 0
    assert first == second
    assert first.state == "SUCCEEDED"
    assert len(calls) == 1
    assert provider.cancel(first.execution_id).state == "CANCELED"


def test_resource_guard_and_router_never_force_heavy_work_local() -> None:
    guard = LocalResourceGuard(min_available_ram_mb=1024, max_running_jobs=1)
    router = ComputeRouter(guard)
    healthy = ResourceSnapshot(4096, 0.2, 2, 0)
    light = router.route(spec(), healthy, BudgetLimits(), BudgetUsage(), ProviderAvailability())
    heavy = router.route(
        spec(JobClass.HEAVY, cost="0.01"),
        healthy,
        BudgetLimits(),
        BudgetUsage(),
        ProviderAvailability(),
    )
    assert light.state == ComputeState.QUEUED
    assert light.provider and light.provider.value == "local"
    assert heavy.state == ComputeState.CLOUD_DISABLED
    assert heavy.provider is None
    constrained = guard.evaluate(
        JobClass.STANDARD,
        ResourceEstimate(Decimal("1"), 512, 10),
        ResourceSnapshot(900, 0.1, 2, 0),
    )
    assert not constrained.allowed


@pytest.mark.parametrize(
    ("limits", "usage", "cost", "reason"),
    [
        (BudgetLimits(cloud_enabled=False), BudgetUsage(), "0.01", "cloud_compute_disabled"),
        (
            BudgetLimits(cloud_enabled=True, spend_cap_blocked=True),
            BudgetUsage(),
            "0.01",
            "cloud_run_spend_cap_blocked",
        ),
        (BudgetLimits(cloud_enabled=True), BudgetUsage(), "0.26", "per_job_cost_limit"),
        (
            BudgetLimits(cloud_enabled=True),
            BudgetUsage(daily_usd=Decimal("0.49")),
            "0.02",
            "daily_cost_limit",
        ),
        (
            BudgetLimits(cloud_enabled=True),
            BudgetUsage(monthly_usd=Decimal("4.99")),
            "0.02",
            "monthly_cost_limit",
        ),
    ],
)
def test_budget_boundaries(
    limits: BudgetLimits, usage: BudgetUsage, cost: str, reason: str
) -> None:
    assert evaluate_budget(Decimal(cost), 30, 1, limits, usage).reason == reason


class FakeCloudTransport:
    def __init__(self) -> None:
        self.payload: dict[str, Any] = {}
        self.request_id = ""

    def post(self, path: str, payload: dict[str, Any], *, request_id: str) -> dict[str, Any]:
        self.payload = {"path": path, **payload}
        self.request_id = request_id
        return {"name": "projects/p/locations/us-east1/executions/fixture"}

    def get(self, path: str) -> dict[str, Any]:
        return {"state": "CLOUD_RUNNING", "path": path}


def test_cloud_run_request_serialization_and_outage() -> None:
    configuration = CloudRunConfiguration(
        "project",
        "us-east1",
        "mil-worker",
        "us-east1-docker.pkg.dev/project/mil/worker@sha256:" + "a" * 64,
        "mil-input",
        "mil-result",
        "worker@project.iam.gserviceaccount.com",
    )
    transport = FakeCloudTransport()
    provider = GoogleCloudRunJobsProvider(configuration, transport)
    execution = provider.submit(spec(JobClass.HEAVY, cost="0.01"))
    override = transport.payload["overrides"]
    assert execution.execution_id.endswith("fixture")
    assert transport.request_id == "phase5-unit"
    assert override["taskCount"] == 1
    assert override["timeout"] == "30s"
    assert provider.cancel(execution.execution_id).state == "CANCELED"
    assert str(transport.payload["path"]).endswith(":cancel")
    assert GoogleCloudRunJobsProvider(configuration).health().detail == (
        "cloud_run_authentication_unavailable"
    )


def test_manifest_checksums_rejection_and_deterministic_sharding() -> None:
    items = [{"symbol": "AAPL"}, {"symbol": "MSFT"}, {"symbol": "SPY"}]
    shards = deterministic_shards(items, 2)
    assert sorted(item["symbol"] for shard in shards for item in shard) == ["AAPL", "MSFT", "SPY"]
    partitions = [(index, shard) for index, shard in enumerate(shards)]
    merged = deterministic_merge(partitions, task_count=2, identity=lambda item: item["symbol"])
    assert [item["symbol"] for item in merged] == ["AAPL", "MSFT", "SPY"]
    with pytest.raises(ValueError, match="complete"):
        deterministic_merge(partitions[:1], task_count=2, identity=lambda item: item["symbol"])
    job_id = uuid4()
    manifest: dict[str, Any] = {
        "job_id": str(job_id),
        "workspace_id": str(LEGACY_WORKSPACE_ID),
        "input_manifest_hash": "a" * 64,
        "algorithm_version": "fixture-v1",
        "partitions": [
            {"index": 0, "uri": "gs://result/0.json", "checksum": "b" * 64},
            {"index": 1, "uri": "gs://result/1.json", "checksum": "c" * 64},
        ],
    }
    manifest["manifest_checksum"] = canonical_checksum(manifest)
    assert validate_result_manifest(
        manifest,
        job_id=job_id,
        workspace_id=LEGACY_WORKSPACE_ID,
        input_manifest_hash="a" * 64,
        algorithm_version="fixture-v1",
        expected_partitions=2,
    ).valid
    manifest["partitions"] = manifest["partitions"][:1]
    rejected = validate_result_manifest(
        manifest,
        job_id=job_id,
        workspace_id=LEGACY_WORKSPACE_ID,
        input_manifest_hash="a" * 64,
        algorithm_version="fixture-v1",
        expected_partitions=2,
    )
    assert not rejected.valid
    assert "partitions_incomplete_or_duplicate" in rejected.errors


def test_cloud_worker_shards_without_changing_fixture_results() -> None:
    bundle = {
        "job_id": "job",
        "workspace_id": "workspace",
        "job_type": "deterministic_fixture",
        "input_manifest_hash": "a" * 64,
        "algorithm_version": "fixture-v1",
        "items": ["alpha", "beta", "gamma", "delta"],
    }
    one = execute_partition(bundle, task_index=0, task_count=1)
    many = [execute_partition(bundle, task_index=index, task_count=2) for index in range(2)]
    combined = deterministic_merge(
        ((int(item["index"]), item["items"]) for item in many),
        task_count=2,
        identity=lambda item: str(item["identity"]),
    )
    assert combined == sorted(one["items"], key=lambda item: str(item["identity"]))


def test_job_idempotency_cloud_disabled_cancel_and_live_boundary(client: TestClient) -> None:
    payload = {
        "submission_key": "heavy-double-click",
        "job_type": "deterministic_fixture",
        "job_class": "HEAVY",
        "estimate": {
            "cpu": "2",
            "ram_mb": 2048,
            "runtime_seconds": 120,
            "estimated_cost_usd": "0.02",
        },
        "parameters": {"execution_mode": "research"},
        "input_manifest": {"fixture": True},
    }
    first = client.post("/api/v1/compute/jobs", json=payload)
    second = client.post("/api/v1/compute/jobs", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["job"]["id"] == second.json()["job"]["id"]
    assert first.json()["job"]["state"] == "CLOUD_DISABLED"
    assert second.json()["created"] is False
    canceled = client.post(f"/api/v1/compute/jobs/{first.json()['job']['id']}/cancel")
    assert canceled.json()["state"] == "CANCELED"
    payload["submission_key"] = "real-order-rejected"
    payload["parameters"] = {"live_order": True, "execution_mode": "live"}
    assert client.post("/api/v1/compute/jobs", json=payload).status_code == 422


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)


def retryable_job(provider: ComputeProviderName, execution_id: str | None = None) -> ComputeJob:
    return ComputeJob(
        id=uuid4(),
        workspace_id=LEGACY_WORKSPACE_ID,
        requested_by_user_id=LEGACY_USER_ID,
        state=ComputeState.FAILED_RETRYABLE.value,
        selected_provider=provider.value,
        cloud_execution_id=execution_id,
        parameters={},
        attempt_count=1,
        max_attempts=3,
    )


def test_retry_is_bounded_and_never_blindly_duplicates_cloud_execution() -> None:
    session = cast(Session, FakeSession())
    local = retry_job(session, retryable_job(ComputeProviderName.LOCAL))
    assert local.state == ComputeState.QUEUED.value
    recorded = retry_job(
        session,
        retryable_job(
            ComputeProviderName.GOOGLE_CLOUD_RUN_JOBS,
            "projects/p/locations/r/executions/e",
        ),
    )
    assert recorded.state == ComputeState.CLOUD_QUEUED.value
    ambiguous = retryable_job(ComputeProviderName.GOOGLE_CLOUD_RUN_JOBS)
    with pytest.raises(ValueError, match="absence must be confirmed"):
        retry_job(session, ambiguous)
    retry_job(session, ambiguous, confirm_no_cloud_execution=True)
    assert ambiguous.state == ComputeState.CLOUD_SUBMITTING.value
    exhausted = retryable_job(ComputeProviderName.LOCAL)
    exhausted.attempt_count = exhausted.max_attempts
    retry_job(session, exhausted)
    assert exhausted.state == ComputeState.FAILED_FINAL.value


def test_cloud_cancel_is_sent_by_supervisor_instead_of_only_changing_local_state() -> None:
    session = cast(Session, FakeSession())
    job = retryable_job(
        ComputeProviderName.GOOGLE_CLOUD_RUN_JOBS,
        "projects/p/locations/r/executions/e",
    )
    job.state = ComputeState.CLOUD_RUNNING.value
    cancel_job(session, job)
    assert job.state == ComputeState.CLOUD_RUNNING.value
    assert job.parameters["cancel_requested"] is True


def test_sessions_freshness_stale_signal_and_alert_deduplication(engine: Engine) -> None:
    assert market_session_state(datetime(2026, 8, 10, 14, 0, tzinfo=UTC)) == (
        MarketSessionState.REGULAR
    )
    assert market_session_state(datetime(2026, 8, 10, 12, 0, tzinfo=UTC)) == (
        MarketSessionState.PREMARKET
    )
    assert market_session_state(datetime(2026, 8, 8, 14, 0, tzinfo=UTC)) == (
        MarketSessionState.CLOSED
    )
    received = datetime(2026, 8, 10, 14, 0, tzinfo=UTC)
    freshness = classify_freshness(
        "fixture",
        datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        received,
        received,
    )
    assert freshness.classification == FreshnessClassification.STALE
    candidate = SignalCandidate(
        "AAPL",
        Decision.BUY,
        Decimal("0.90"),
        "1d",
        "fixture",
        {},
        {},
        {},
        {},
        [],
        {},
        [],
        {},
        "close below support",
        {},
        "fixture-v1",
        {},
        freshness,
    )
    downgraded = evaluate_signal(candidate)
    assert downgraded.decision == Decision.WATCH
    assert downgraded.confidence == Decimal("0.25")
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        session.info["workspace_id"] = LEGACY_WORKSPACE_ID
        alert = AlertCandidate(
            LEGACY_WORKSPACE_ID,
            "stale_market_feed",
            "warning",
            "fixture-stale-feed",
            "Stale feed",
            "Fixture feed is stale",
            {},
        )
        channel = InAppAlertChannel()
        first, created = channel.deliver(session, alert)
        second, duplicate_created = channel.deliver(session, alert)
        assert first.id == second.id
        assert created and not duplicate_created
        assert second.occurrence_count == 2


def test_paper_live_execution_boundary() -> None:
    assert_research_or_paper_only({"execution_mode": "paper"})
    with pytest.raises(ValueError, match="forbidden"):
        assert_research_or_paper_only({"brokerage_credentials": "secret"})
    with pytest.raises(ValueError, match="forbidden"):
        assert_research_or_paper_only({"nested": {"real_order": True}})
    with pytest.raises(ValueError, match="paper"):
        assert_research_or_paper_only({"execution_mode": "live"})
