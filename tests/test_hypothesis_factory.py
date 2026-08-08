from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import func, select

from packages.database.models import (
    LEGACY_WORKSPACE_ID,
    CandidateFeatureSpec,
    ExperimentManifest,
    FactorExperiment,
    FactorExperimentFold,
    MultipleTestingResult,
    NegativeControlResult,
    ResearchHypothesis,
    ResearchPromotionEvent,
    RobustnessResult,
)
from packages.database.session import make_session_factory, session_scope
from packages.hypothesis.dsl import execute_operations, validate_feature_spec
from packages.hypothesis.engines import QlibResearchEngine, RDAgentResearchEngine
from packages.hypothesis.fixtures import seed_reference_hypothesis_research
from packages.hypothesis.lifecycle import (
    transition_hypothesis,
    validate_promotion_transition,
)
from packages.hypothesis.reasoning import (
    DeterministicReasoningProvider,
    RuntimeModelReasoningProvider,
)
from packages.hypothesis.types import (
    HypothesisStatus,
    PromotionStage,
    ReasoningRequest,
    TimePartition,
)
from packages.hypothesis.validation import (
    adjust_p_values,
    aggregate_ic,
    deterministic_negative_controls,
    expanding_walk_forward,
    factor_statistics,
    incremental_information_test,
    purged_cross_validation,
    validate_leakage_fixture,
    validate_partition,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _spec() -> dict[str, object]:
    return {
        "feature_key": "safe_feature",
        "required_datasets": ["fixture.data"],
        "required_graph_paths": [{"driver": "fixture"}],
        "transformations": [
            {"operation": "rolling_mean", "window": 3},
            {"operation": "zscore"},
        ],
        "aggregation": {},
        "lookback": 90,
        "lag": 1,
        "weighting": {},
        "missing_data_policy": "mark_missing",
        "normalization": "train_only_zscore",
        "expected_direction": "negative",
        "required_output": "numeric",
        "temporal_policy": {"simulation_eligible_only": True},
        "implementation_version": 1,
        "generator": "test",
    }


def test_hypothesis_lifecycle_rejects_invalid_shortcuts() -> None:
    hypothesis = ResearchHypothesis(status="DRAFT")
    with pytest.raises(ValueError, match="DRAFT -> VALIDATED"):
        transition_hypothesis(hypothesis, HypothesisStatus.VALIDATED)
    transition_hypothesis(hypothesis, HypothesisStatus.EVIDENCE_REQUIRED)
    transition_hypothesis(hypothesis, HypothesisStatus.READY_FOR_IMPLEMENTATION)
    assert hypothesis.status == "READY_FOR_IMPLEMENTATION"


def test_research_promotion_requires_every_gate() -> None:
    assert validate_promotion_transition(None, PromotionStage.DRAFT) is PromotionStage.DRAFT
    assert (
        validate_promotion_transition(PromotionStage.DRAFT, PromotionStage.EVIDENCE_CHECKED)
        is PromotionStage.EVIDENCE_CHECKED
    )
    with pytest.raises(ValueError, match="invalid promotion transition"):
        validate_promotion_transition(PromotionStage.DRAFT, PromotionStage.PAPER_ELIGIBLE)


def test_feature_dsl_is_declarative_bounded_and_deterministic() -> None:
    specification = _spec()
    validate_feature_spec(specification)
    first = execute_operations([1, 2, 3, 4, 5], specification["transformations"])  # type: ignore[arg-type]
    second = execute_operations([1, 2, 3, 4, 5], specification["transformations"])  # type: ignore[arg-type]
    np.testing.assert_equal(first, second)
    unsafe = {**specification, "transformations": [{"operation": "python", "code": "open('x')"}]}
    with pytest.raises(ValueError, match="unsupported operation"):
        validate_feature_spec(unsafe)
    leaked = {**specification, "temporal_policy": {"simulation_eligible_only": False}}
    with pytest.raises(ValueError, match="simulation-eligible"):
        validate_feature_spec(leaked)


def test_train_validation_test_boundaries_cannot_overlap() -> None:
    invalid = TimePartition(
        train_start=NOW,
        train_end=NOW + timedelta(days=30),
        validation_start=NOW + timedelta(days=20),
        validation_end=NOW + timedelta(days=40),
        test_start=NOW + timedelta(days=41),
        test_end=NOW + timedelta(days=50),
    )
    with pytest.raises(ValueError, match="must not overlap"):
        validate_partition(invalid)


def test_walk_forward_and_skfolio_purging_embargo_are_explicit() -> None:
    folds = expanding_walk_forward(
        start=NOW,
        train_days=180,
        validation_days=30,
        test_days=30,
        folds=3,
        purge_days=5,
        embargo_days=7,
    )
    assert len(folds) == 3
    assert all(item.purge_observations == 5 and item.embargo_observations == 7 for item in folds)
    cv = purged_cross_validation(
        n_folds=6, n_test_folds=2, purge_observations=5, embargo_observations=7
    )
    assert cv.purged_size == 5
    assert cv.embargo_size == 7


def test_factor_statistics_include_ic_quantiles_coverage_and_decay_inputs() -> None:
    factor = np.linspace(-1, 1, 100)
    outcome = factor * 0.2 + np.sin(np.arange(100)) * 0.01
    metrics = factor_statistics(factor, outcome)
    assert metrics.pearson_ic > 0.9
    assert metrics.spearman_ic > 0.9
    assert metrics.quantile_monotonicity > 0.8
    assert metrics.top_minus_bottom > 0
    assert metrics.coverage == 1
    aggregate = aggregate_ic([0.04, 0.02, -0.01, 0.03])
    assert set(aggregate) == {
        "mean_ic",
        "ic_std",
        "ic_information_ratio",
        "positive_fold_rate",
    }


@pytest.mark.parametrize("method", ["bonferroni", "holm", "benjamini-hochberg"])
def test_multiple_testing_never_loses_raw_or_adjusted_p_values(method: str) -> None:
    results = adjust_p_values([0.001, 0.02, 0.20], method=method)
    assert all(item["number_of_hypotheses"] == 3 for item in results)
    assert all(item["correction_method"] == method for item in results)
    assert all("raw_p_value" in item and "adjusted_p_value" in item for item in results)


def test_conventional_baseline_incremental_information_is_out_of_sample() -> None:
    generator = np.random.default_rng(42)
    baseline = generator.normal(size=(120, 3))
    candidate = generator.normal(size=120)
    outcome = baseline[:, 0] * 0.4 + candidate * 0.5 + generator.normal(0, 0.05, 120)
    result = incremental_information_test(baseline, candidate, outcome, train_size=80)
    assert result["mse_improvement"] > 0
    assert result["candidate_adds_information"] == 1.0


def test_negative_controls_are_deterministic_and_leakage_attacks_are_rejected() -> None:
    first = deterministic_negative_controls(range(30), 99)
    second = deterministic_negative_controls(range(30), 99)
    for key in first:
        np.testing.assert_equal(first[key], second[key])
    attacks = [
        "future_alfred_vintage",
        "future_sec_disclosure",
        "future_graph_relationship",
        "future_feature_revision",
        "future_universe_membership",
        "future_normalization",
        "future_publication_time",
        "target_label_leakage",
        "post_event_identifier",
    ]
    for attack in attacks:
        with pytest.raises(ValueError, match="temporally contaminated"):
            validate_leakage_fixture({attack: True})


def test_reasoning_providers_are_bounded_optional_and_archetype_specific() -> None:
    provider = DeterministicReasoningProvider()
    titles = []
    for archetype in ("semiconductor", "airline", "agriculture"):
        candidates = provider.generate_hypotheses(
            ReasoningRequest(
                subject={"archetype": archetype},
                graph_paths=({"driver": archetype},),
                evidence=(),
                datasets=(),
                maximum_hypotheses=1,
            )
        )
        titles.append(candidates[0].title)
    assert len(set(titles)) == 3
    unavailable = RuntimeModelReasoningProvider()
    assert unavailable.available() is False
    with pytest.raises(RuntimeError, match="unavailable"):
        unavailable.generate_hypotheses(
            ReasoningRequest(subject={}, graph_paths=(), evidence=(), datasets=())
        )


def test_optional_engine_fixtures_do_not_execute_external_code() -> None:
    qlib = QlibResearchEngine()
    qlib_result = qlib.fixture_run(
        {
            "feature_snapshot_id": "fixture",
            "universe_version_id": "fixture",
            "partitions": {"sealed": True},
            "seed": 42,
        }
    )
    assert qlib_result["input_authority"] == "market-intelligence-lab"
    rd_agent = RDAgentResearchEngine()
    result = rd_agent.fixture_artifact({"hypothesis_id": "fixture", "maximum_candidates": 2})
    assert result["executed_generated_code"] is False
    assert result["automatically_merged"] is False
    assert rd_agent.status().enabled is False


def test_reference_factory_is_reproducible_distinct_and_includes_rejection(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        result = seed_reference_hypothesis_research(session, LEGACY_WORKSPACE_ID)
        repeat = seed_reference_hypothesis_research(session, LEGACY_WORKSPACE_ID)
        assert result["hypothesis_count"] == repeat["hypothesis_count"] == 3
        assert result["experiment_count"] == 3
        assert result["fold_count"] == 9
        assert result["rejected_hypotheses"] == 1
        assert result["negative_controls"] == 12
        assert result["runtime_model_requests"] == result["ai_tokens"] == 0
        titles = [item["title"] for item in result["archetypes"]]
        assert len(set(titles)) == 3
        assert session.scalar(select(func.count(CandidateFeatureSpec.id))) == 3
        assert session.scalar(select(func.count(FactorExperimentFold.id))) == 9
        assert session.scalar(select(func.count(MultipleTestingResult.id))) == 9
        assert session.scalar(select(func.count(RobustnessResult.id))) == 21
        assert session.scalar(select(func.count(NegativeControlResult.id))) == 12
        assert session.scalar(select(func.count(ExperimentManifest.id))) == 3
        assert session.scalar(select(func.count(ResearchPromotionEvent.id))) >= 18


def test_completed_experiment_is_immutable(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        seed_reference_hypothesis_research(session, LEGACY_WORKSPACE_ID)
    session = factory()
    try:
        experiment = session.scalar(
            select(FactorExperiment).where(FactorExperiment.status == "COMPLETED")
        )
        assert experiment is not None
        experiment.seed += 1
        with pytest.raises(ValueError, match="immutable"):
            session.flush()
        session.rollback()
    finally:
        session.close()


def test_hypothesis_api_workflow_and_engine_status(client) -> None:  # type: ignore[no-untyped-def]
    fixture = client.post("/api/v1/hypotheses/reference-fixture")
    assert fixture.status_code == 201
    hypotheses = client.get("/api/v1/hypotheses").json()
    assert hypotheses["total"] == 3
    rejected = next(item for item in hypotheses["items"] if item["status"] == "REJECTED")
    detail = client.get(f"/api/v1/hypotheses/{rejected['id']}")
    assert detail.status_code == 200
    assert detail.json()["semantics"] == "research_hypothesis_not_investment_prediction"
    experiments = client.get("/api/v1/factor-experiments").json()
    experiment_id = experiments["items"][0]["id"]
    folds = client.get(f"/api/v1/factor-experiments/{experiment_id}/folds").json()
    assert folds["total"] == 3
    assert folds["failed_folds_are_retained"] is True
    statistics = client.get(f"/api/v1/factor-experiments/{experiment_id}/statistics").json()
    assert statistics["raw_p_values_never_reported_alone"] is True
    robustness = client.get(f"/api/v1/factor-experiments/{experiment_id}/robustness").json()
    assert len(robustness["negative_controls"]) == 4
    promotions = client.get(f"/api/v1/hypotheses/{rejected['id']}/promotion-events").json()
    assert promotions["items"][-1]["to_stage"] == "REJECTED"
    assert client.get("/api/v1/research-engines/qlib").status_code == 200
    rd_status = client.get("/api/v1/research-engines/rd-agent").json()
    assert rd_status["enabled"] is False
