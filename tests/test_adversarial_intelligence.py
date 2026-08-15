from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from packages.adversarial_intelligence.service import (
    alternative_explanation,
    confidence_profile,
    generate_challenges,
    propagate_scenario,
    resolve_challenge,
    review_status,
    run_counterfactual,
    sensitivity_curve,
    transmission_value,
)


def supported_edges() -> list[dict[str, object]]:
    return [
        {
            "source": "electricity",
            "target": "facility",
            "relationship": "powers",
            "supported": True,
            "confidence": 0.9,
            "weight": 0.5,
            "function": "WEIGHTED_EXPOSURE",
            "lag": 1,
        },
        {
            "source": "facility",
            "target": "company",
            "relationship": "operates",
            "supported": True,
            "confidence": 0.8,
            "weight": 0.7,
            "function": "CAPACITY_WEIGHTED",
            "lag": 0,
        },
        {
            "source": "company",
            "target": "electricity",
            "relationship": "cycle",
            "supported": True,
            "confidence": 1.0,
            "weight": 1.0,
        },
        {
            "source": "electricity",
            "target": "unsupported-company",
            "relationship": "invented",
            "supported": False,
            "confidence": 1.0,
            "weight": 1.0,
        },
    ]


def test_critical_entity_ambiguity_blocks_apparently_strong_hypothesis() -> None:
    challenges = generate_challenges({"claim": "strong OOS result", "entity_ambiguous": True})
    assert challenges[0]["category"] == "ENTITY_RESOLUTION"
    assert review_status(challenges) == "BLOCKED"
    assert all("BUY" not in item["challenge"] for item in challenges)


def test_challenge_resolution_requires_test_evidence() -> None:
    challenge = generate_challenges({"low_coverage": True})[0]
    with pytest.raises(ValueError, match="referenced test"):
        resolve_challenge(challenge, {"note": "prose alone"})
    resolved = resolve_challenge(challenge, {"test_id": "coverage-1", "result_checksum": "a" * 64})
    assert resolved["status"] == "RESOLVED"


def test_alternative_explanation_eliminates_incremental_information() -> None:
    result = alternative_explanation(0.20, 0.005)
    assert result["incremental_information_retained"] is False
    assert result["challenge_categories"] == ["ALTERNATIVE_EXPLANATION", "FACTOR_REDUNDANCY"]


def test_scenario_uses_supported_paths_and_is_cycle_safe() -> None:
    impacts = propagate_scenario([{"target": "electricity", "value": 0.2}], supported_edges())
    assert [item["subject"] for item in impacts] == ["facility", "company"]
    assert all(item["subject"] != "unsupported-company" for item in impacts)
    assert impacts[-1]["transmission_path"][-1]["lag"] == 0


@pytest.mark.parametrize(
    "kind",
    [
        "LINEAR",
        "BOUNDED_LINEAR",
        "THRESHOLD",
        "LAGGED",
        "WEIGHTED_EXPOSURE",
        "CAPACITY_WEIGHTED",
        "LOCATION_WEIGHTED",
        "BINARY_DISRUPTION",
    ],
)
def test_transmission_functions_are_constrained(kind: str) -> None:
    assert isinstance(
        transmission_value(kind, 0.2, {"weight": 0.5, "bound": 0.05, "threshold": 0.1}), float
    )


def test_sensitivity_retains_all_scenarios() -> None:
    curve = sensitivity_curve([0.1, 0.2, 0.3], supported_edges()[:2], "company")
    assert len(curve["points"]) == 3
    assert curve["classification"] == "MONOTONIC"


def test_counterfactual_is_isolated_and_not_causal_by_default() -> None:
    reference = {"drivers": {"electricity": 0.2, "fuel": 0.1}, "evidence": ["source-1"]}
    canonical = copy.deepcopy(reference)
    result = run_counterfactual(reference, {"operation": "REMOVE_DRIVER", "target": "electricity"})
    assert reference == canonical
    assert "electricity" not in result["counterfactual"]["drivers"]
    assert result["identification_status"] == "SIMULATED_MECHANISM"


def test_confidence_exposes_every_component_and_is_not_probability() -> None:
    profile = confidence_profile({"evidence_quality": 0.9, "temporal_safety": 1.0})
    assert len(profile["components"]) == 13
    assert profile["semantics"] == "transparent_research_index_not_probability_or_profit_forecast"


def test_future_information_does_not_enter_deterministic_review() -> None:
    historical = {"low_coverage": True, "as_of": "2025-01-01"}
    future = {**historical, "memory_contradiction": True, "simulation_eligible_time": "2026-01-01"}
    as_of_inputs = {key: value for key, value in future.items() if key != "memory_contradiction"}
    assert len(generate_challenges(as_of_inputs)) == 1


def test_protected_reference_api_builds_three_cases_and_runs_simulations(
    client: TestClient,
) -> None:
    assert client.post("/api/v1/research/intelligence/reference-fixture").status_code == 200
    seeded = client.post("/api/v1/research/adversarial/reference-fixture")
    assert seeded.status_code == 200, seeded.text
    assert seeded.json() == {
        "research_case_count": 3,
        "review_count": 3,
        "blocked_count": 1,
        "scenario_count": 3,
        "counterfactual_count": 3,
        "no_trade_recommendations": True,
    }
    reviews = client.get("/api/v1/research/skeptic/reviews").json()["items"]
    assert {item["status"] for item in reviews} == {"BLOCKED", "NEEDS_EVIDENCE"}
    scenarios = client.get("/api/v1/research/scenarios").json()["items"]
    scenario_run = client.post(f"/api/v1/research/scenarios/{scenarios[0]['id']}/run")
    assert scenario_run.status_code == 200
    assert scenario_run.json()["warning"] == "THIS IS A SCENARIO, NOT A FORECAST"
    counterfactuals = client.get("/api/v1/research/counterfactuals").json()["items"]
    counterfactual_run = client.post(
        f"/api/v1/research/counterfactuals/{counterfactuals[0]['id']}/run"
    )
    assert counterfactual_run.status_code == 200
    assert counterfactual_run.json()["identification_status"] == "SIMULATED_MECHANISM"
