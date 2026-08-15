from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from packages.database.models import (
    DivergenceEvent,
    HypothesisMemoryDecision,
    ResearchMemoryEntry,
    SignalIndependenceAnalysis,
)
from packages.research_intelligence.service import (
    independence_components,
    pearson,
    revalidate_memory,
    spearman,
    weaken_memory,
)


def _seed(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/research/intelligence/reference-fixture")
    assert response.status_code == 200, response.text
    return response.json()


def test_reference_memory_is_positive_negative_applicable_and_searchable(
    client: TestClient,
) -> None:
    summary = _seed(client)
    assert summary["memory_count"] == 3
    assert summary["negative_memory_count"] == 1
    response = client.get("/api/v1/research/memory")
    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["conclusion"] for item in items} == {"POSITIVE", "NEGATIVE"}
    agriculture = next(item for item in items if item["conclusion"] == "NEGATIVE")
    assert agriculture["failure_reasons"]
    assert agriculture["applicability"]["business_model"]
    assert agriculture["result_summary"]["oos"]
    search = client.get("/api/v1/research/memory/search", params={"conclusion": "negative"})
    assert search.status_code == 200
    assert len(search.json()["items"]) == 1


def test_known_failure_is_suppressed_and_override_is_audited(client: TestClient) -> None:
    summary = _seed(client)
    assert summary["known_failure_suppressed"] is True
    assert summary["authorized_override_recorded"] is True
    negative = next(
        item
        for item in client.get("/api/v1/research/memory").json()["items"]
        if item["conclusion"] == "NEGATIVE"
    )
    detail = client.get(f"/api/v1/research/memory/{negative['id']}")
    decisions = detail.json()["memory_decisions"]
    assert any(
        item["classification"] == "KNOWN_FAILURE" and item["decision"] == "SUPPRESSED"
        for item in decisions
    )
    assert any(
        item["classification"] == "KNOWN_FAILURE"
        and item["decision"] == "SCHEDULE_ALLOWED"
        and item["override_authorized"]
        for item in decisions
    )


def test_redundant_factor_differs_from_independent_factor(client: TestClient) -> None:
    _seed(client)
    analyses = client.get("/api/v1/research/signal-independence").json()["items"]
    redundant = next(item for item in analyses if "overlap" in item["factor_key"])
    independent = next(item for item in analyses if "independent" in item["factor_key"])
    assert float(redundant["predictive_strength"]) > 0.9
    assert float(redundant["redundancy_score"]) > 0.9
    assert float(independent["redundancy_score"]) < float(redundant["redundancy_score"])
    assert float(independent["independent_information_score"]) > float(
        redundant["independent_information_score"]
    )
    assert independent["formula"]["version"] == "independent-information-score-v1"


def test_divergence_is_detected_without_trade_eligibility(client: TestClient) -> None:
    summary = _seed(client)
    assert summary["divergence_count"] == 1
    assert summary["paper_eligible_from_divergence"] is False
    event = client.get("/api/v1/research/divergence-events").json()["items"][0]
    assert event["status"] == "DETECTED"
    assert event["paper_eligible"] is False
    assert float(event["domain_values"]["fundamentals"]["normalized"]) > 0
    assert float(event["domain_values"]["external_driver"]["normalized"]) < 0
    assert event["historical_analogues"][0]["sample_size"] == 1
    assert "tiny" in event["historical_analogues"][0]["warning"]


def test_temporal_truth_blocks_future_memory_and_divergence(client: TestClient) -> None:
    _seed(client)
    memories = client.get("/api/v1/research/memory").json()["items"]
    earliest_memory = min(
        datetime.fromisoformat(item["simulation_eligible_time"]) for item in memories
    )
    before_memory = client.get(
        "/api/v1/research/memory",
        params={"as_of": (earliest_memory - timedelta(seconds=1)).isoformat()},
    )
    assert before_memory.json()["items"] == []
    event = client.get("/api/v1/research/divergence-events").json()["items"][0]
    event_time = datetime.fromisoformat(event["as_of_time"])
    before_event = client.get(
        "/api/v1/research/divergence-events",
        params={"as_of": (event_time - timedelta(seconds=1)).isoformat()},
    )
    assert before_event.json()["items"] == []


def test_contradictions_regimes_clusters_and_efficiency_are_explainable(
    client: TestClient,
) -> None:
    _seed(client)
    contradiction = client.get("/api/v1/research/contradictions").json()["items"][0]
    assert contradiction["causally_explained"] is False
    regimes = client.get("/api/v1/research/regimes").json()
    assert regimes["definitions"][0]["method"]["no_future_data"] is True
    clusters = client.get("/api/v1/research/factor-clusters").json()
    assert clusters["causal_structure_claimed"] is False
    information = client.get("/api/v1/research/information-value").json()
    assert information["semantics"] == "research_resource_efficiency_not_investment_roi"
    methods = client.get("/api/v1/research/method-reliability").json()["items"]
    assert all("sample" in item["interpretation"].lower() for item in methods)
    attribution = client.get("/api/v1/research/outcome-attribution").json()["items"]
    assert {item["category"] for item in attribution} == {"success", "failure"}


def test_statistics_are_deterministic_and_distinguish_rank_from_linear() -> None:
    left = [1.0, 2.0, 3.0, 4.0, 5.0]
    right = [2.0, 4.0, 6.0, 8.0, 10.0]
    outcome = [1.0, 2.2, 2.8, 4.1, 5.2]
    assert pearson(left, right) == pytest.approx(1.0)
    assert spearman(left, right) == pytest.approx(1.0)
    components = independence_components(left, right, outcome)
    assert set(components) >= {
        "partial_correlation",
        "residual_contribution",
        "incremental_rank_ic",
        "redundancy_score",
        "independent_information_score",
    }


def test_memory_weakening_revalidation_and_immutability(client: TestClient, engine: Engine) -> None:
    _seed(client)
    with Session(engine) as session:
        memory = session.scalar(select(ResearchMemoryEntry).order_by(ResearchMemoryEntry.id))
        assert memory is not None
        weaken_memory(memory, "feature implementation changed", datetime.now(UTC))
        session.commit()
        assert memory.status == "WEAK"
        revalidate_memory(memory, "new OOS validation passed", datetime.now(UTC))
        session.commit()
        assert memory.status == "ACTIVE"
        memory.conclusion = "NEGATIVE" if memory.conclusion == "POSITIVE" else "POSITIVE"
        with pytest.raises(ValueError, match="immutable"):
            session.commit()


def test_workspace_scope_covers_new_research_intelligence_records(
    client: TestClient, engine: Engine
) -> None:
    _seed(client)
    with Session(engine) as session:
        assert session.scalar(select(ResearchMemoryEntry)) is not None
        assert session.scalar(select(SignalIndependenceAnalysis)) is not None
        assert session.scalar(select(DivergenceEvent)) is not None
        decisions = list(session.scalars(select(HypothesisMemoryDecision)))
        assert len(decisions) == 2
