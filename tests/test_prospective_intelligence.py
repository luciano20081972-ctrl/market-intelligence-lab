from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from packages.prospective_intelligence.service import (
    CalibrationState,
    EvaluationMode,
    ForecastType,
    aggregate_scores,
    allocation_priority,
    calibration_bins,
    confidence_calibration,
    construct_portfolio,
    create_forecast,
    eligibility,
    observe_outcome,
    portfolio_evaluation,
    rebalance_orders,
    research_risk,
    scenario_stress,
    score_forecast,
)


def forecast():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return create_forecast(
        id="forecast-1",
        workspace_id="workspace-1",
        target_definition={"key": "revenue-growth", "version": 1},
        forecast_type="PROBABILITY",
        forecast_value=0.7,
        evaluation_mode="PROSPECTIVE",
        as_of_time=now,
        target_start_time=now + timedelta(days=1),
        target_end_time=now + timedelta(days=90),
        outcome_eligible_time=now + timedelta(days=91),
        manifest={"software_sha": "abc", "alembic_revision": "4e398fc4c9a1"},
    )


def test_forecast_lock_is_frozen_and_precedes_outcome() -> None:
    item = forecast().lock(datetime(2026, 1, 2, tzinfo=UTC))
    assert item.state == "LOCKED"
    with pytest.raises(FrozenInstanceError):
        item.forecast_value = 0.9  # type: ignore[misc]
    with pytest.raises(ValueError, match="already locked"):
        item.lock(datetime(2026, 1, 3, tzinfo=UTC))


def test_forecast_cannot_lock_after_eligibility() -> None:
    with pytest.raises(ValueError, match="before outcome"):
        forecast().lock(datetime(2027, 1, 1, tzinfo=UTC))


def test_outcome_maturity_is_release_critical() -> None:
    item = forecast().lock(datetime(2026, 1, 2, tzinfo=UTC))
    with pytest.raises(ValueError, match="not mature"):
        observe_outcome(item, 1, datetime(2026, 2, 1, tzinfo=UTC), {})
    observed = observe_outcome(
        item, 1, datetime(2026, 4, 3, tzinfo=UTC), {"publication": "eligible"}
    )
    assert observed["immutable"] and observed["evaluation_mode"] == "PROSPECTIVE"
    assert item.forecast_value == 0.7


@pytest.mark.parametrize(
    ("kind", "prediction", "actual", "metric"),
    [
        ("DIRECTIONAL", 1, 0.2, "directionally_correct"),
        ("PROBABILITY", 0.8, 1, "brier_score"),
        ("CONTINUOUS", 2.5, 2, "absolute_error"),
        ("INTERVAL", [1, 3], 2, "interval_score"),
        ("RANK", [1, 2, 3], [2, 4, 9], "rank_ic"),
        ("SCENARIO_CONDITIONAL", -1, -0.2, "directionally_correct"),
    ],
)
def test_bounded_forecast_scoring(
    kind: str, prediction: object, actual: object, metric: str
) -> None:
    assert metric in score_forecast(kind, prediction, actual)


def test_probability_scoring_penalizes_overconfidence() -> None:
    assert (
        score_forecast("PROBABILITY", 0.99, 0)["brier_score"]
        > score_forecast("PROBABILITY", 0.6, 0)["brier_score"]
    )
    assert (
        score_forecast("PROBABILITY", 0.99, 0)["log_loss"]
        > score_forecast("PROBABILITY", 0.6, 0)["log_loss"]
    )


def test_interval_penalizes_misses() -> None:
    covered = score_forecast("INTERVAL", [0, 2], 1)
    missed = score_forecast("INTERVAL", [0, 2], 3)
    assert covered["covered"] is True and missed["interval_score"] > covered["interval_score"]


def test_calibration_populations_never_mix_and_asof_never_leaks() -> None:
    before = datetime(2026, 2, 1, tzinfo=UTC)
    after = datetime(2026, 3, 1, tzinfo=UTC)
    records = (
        [{"evaluation_mode": "HISTORICAL_REPLAY", "observed_at": before, "brier_score": 0.0}] * 100
        + [{"evaluation_mode": "PROSPECTIVE", "observed_at": before, "brier_score": 0.2}] * 5
        + [{"evaluation_mode": "PROSPECTIVE", "observed_at": after, "brier_score": 0.0}]
    )
    result = aggregate_scores(records, mode="PROSPECTIVE", as_of=before)
    assert result["sample_count"] == 5 and result["mean_brier_score"] == pytest.approx(0.2)
    assert result["status"] == "INSUFFICIENT_SAMPLE"


def test_calibration_bins_show_samples() -> None:
    bins = calibration_bins([0.1, 0.2, 0.8, 0.9], [0, 1, 1, 1], bins=2)
    assert [item["sample_count"] for item in bins] == [2, 2]


def test_confidence_is_not_probability_and_needs_sample() -> None:
    rows = [
        {"evaluation_mode": "PROSPECTIVE", "confidence": 0.8, "quality": 1},
        {"evaluation_mode": "HISTORICAL_REPLAY", "confidence": 1, "quality": 1},
    ]
    result = confidence_calibration(rows)
    assert result["sample_count"] == 1 and result["status"] == "INSUFFICIENT_SAMPLE"
    assert "not_event_probability" in result["semantics"]


def test_critical_skeptic_challenge_blocks_candidate() -> None:
    result = eligibility({"oos": True, "negative_control": True}, CalibrationState.CALIBRATED, True)
    assert (
        not result["eligible"] and "unresolved_critical_skeptic_challenge" in result["failed_gates"]
    )


def test_uncalibrated_candidate_uses_strict_risk() -> None:
    result = eligibility({"oos": True}, CalibrationState.UNCALIBRATED, False)
    assert result["eligible"] and result["risk_tier"] == "STRICT_UNCALIBRATED"


def test_priority_is_transparent_not_alpha() -> None:
    result = allocation_priority({"qualification": 1, "independence": 0.5, "skeptic_penalty": 0.5})
    assert result["formula_version"] == "paper-priority-v1"
    assert "not_expected_alpha" in result["semantics"] and result["components"]


def test_optimizer_is_capped_by_hard_risk_and_cannot_leverage() -> None:
    plan = construct_portfolio(
        {"A": 100, "B": 1, "C": 1, "D": 1, "E": 1}, max_position=0.2, min_cash=0.1
    )
    assert max(plan["weights"].values()) <= 0.2
    assert (
        plan["no_shorting"] and plan["no_leverage"] and sum(plan["weights"].values()) <= 0.9 + 1e-8
    )


def test_information_domain_concentration_is_visible() -> None:
    result = research_risk(
        {"A": 0.2, "B": 0.2, "C": 0.1}, {"A": "macro", "B": "macro", "C": "macro"}, max_domain=0.4
    )
    assert not result["approved"] and "information_domain:macro" in result["violations"]


def test_scenario_stress_can_reject_plan_without_probabilities() -> None:
    result = scenario_stress(
        {"A": 0.5, "B": 0.5}, {"shock": {"A": -0.3, "B": -0.2}}, loss_limit=0.15
    )
    assert not result["approved"] and result["probabilities_assigned"] is False


def test_rebalance_is_preview_only_and_idempotent() -> None:
    first = rebalance_orders({}, {"A": 0.2}, 1000, {"A": 100}, "plan-1")
    second = rebalance_orders({}, {"A": 0.2}, 1000, {"A": 100}, "plan-1")
    assert first == second and first[0]["preview"] and first[0]["paper_only"]
    assert first[0]["side"] == "BUY"


def test_paper_evaluation_is_unambiguously_simulated() -> None:
    result = portfolio_evaluation([100, 105, 102], [100, 101, 101])
    assert result["label"] == "SIMULATED / PAPER ONLY" and result["max_drawdown"] < 0


def test_evaluation_mode_and_forecast_type_are_bounded() -> None:
    assert set(EvaluationMode) == {
        EvaluationMode.PROSPECTIVE,
        EvaluationMode.HISTORICAL_REPLAY,
        EvaluationMode.FIXTURE,
    }
    assert len(ForecastType) == 6
    with pytest.raises(ValueError):
        create_forecast(
            id="x",
            workspace_id="w",
            target_definition={},
            forecast_type="PROBABILITY",
            forecast_value=1.1,
            evaluation_mode="PROSPECTIVE",
            as_of_time=datetime(2026, 1, 1, tzinfo=UTC),
            target_start_time=datetime(2026, 1, 2, tzinfo=UTC),
            target_end_time=datetime(2026, 1, 3, tzinfo=UTC),
            outcome_eligible_time=datetime(2026, 1, 4, tzinfo=UTC),
        )


def test_protected_forecast_api_freezes_observes_and_scores(client: TestClient) -> None:
    created = client.post(
        "/api/v1/research/forecasts",
        json={
            "target_key": "fixture-revenue-growth",
            "forecast_type": "PROBABILITY",
            "forecast_value": {"value": 0.7},
            "evaluation_mode": "FIXTURE",
            "as_of_time": "2026-08-15T12:00:00Z",
            "target_start_time": "2026-08-16T12:00:00Z",
            "target_end_time": "2026-10-01T12:00:00Z",
            "outcome_eligible_time": "2026-10-02T12:00:00Z",
            "manifest": {"fixture": True},
        },
    )
    assert created.status_code == 200
    forecast_id = created.json()["id"]
    locked = client.post(f"/api/v1/research/forecasts/{forecast_id}/lock")
    assert locked.status_code == 200 and locked.json()["state"] == "LOCKED"
    early = client.post(
        f"/api/v1/research/forecasts/{forecast_id}/observe",
        json={
            "realized_value": {"value": 1},
            "observed_at": "2026-09-01T12:00:00Z",
            "source_manifest": {},
        },
    )
    assert early.status_code == 409
    mature = client.post(
        f"/api/v1/research/forecasts/{forecast_id}/observe",
        json={
            "realized_value": {"value": 1},
            "observed_at": "2026-10-03T12:00:00Z",
            "source_manifest": {"eligible": True},
        },
    )
    assert mature.status_code == 200 and mature.json()["immutable"]
    score = client.get(f"/api/v1/research/forecasts/{forecast_id}/score")
    assert score.status_code == 200 and score.json()["metrics"]["brier_score"] == pytest.approx(
        0.09
    )


def test_paper_plan_api_is_preview_only_and_risk_reviewed(client: TestClient) -> None:
    response = client.post(
        "/api/v1/paper/plans",
        json={
            "scores": {"A": 0.9, "B": 0.7, "C": 0.5, "D": 0.4, "E": 0.3},
            "domains": {
                "A": "tech",
                "B": "energy",
                "C": "market",
                "D": "rates",
                "E": "agriculture",
            },
            "prices": {"A": 100, "B": 100, "C": 100, "D": 100, "E": 100},
            "equity": 100000,
        },
    )
    assert response.status_code == 200
    assert response.json()["label"] == "SIMULATED / PAPER ONLY"
    assert response.json()["brokerage_connectivity"] is False
    assert all(order["preview"] for order in response.json()["order_preview"])
