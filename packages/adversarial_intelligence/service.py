from __future__ import annotations

import copy
import hashlib
import json
from collections import deque
from typing import Any

CHALLENGE_CATEGORIES = frozenset(
    {
        "DATA_INTEGRITY",
        "TEMPORAL_LEAKAGE",
        "ENTITY_RESOLUTION",
        "MECHANISM_SUPPORT",
        "CONFOUNDING",
        "ALTERNATIVE_EXPLANATION",
        "REGIME_DEPENDENCE",
        "BASE_RATE",
        "SOURCE_RELIABILITY",
        "DATA_COVERAGE",
        "MODEL_RISK",
        "FACTOR_REDUNDANCY",
        "MULTIPLE_TESTING",
        "SELECTION_BIAS",
        "SURVIVORSHIP_BIAS",
        "NORMALIZATION_RISK",
        "OUTCOME_DEFINITION",
        "PARAMETER_SENSITIVITY",
        "EXECUTION_COST",
        "CONTRADICTING_EVIDENCE",
        "MISSING_EVIDENCE",
    }
)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def generate_challenges(signals: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert mechanical safeguards into structured, reproducible challenges."""
    rules = (
        ("temporal_warning", "TEMPORAL_LEAKAGE", "CRITICAL", "Temporal boundary warning"),
        ("entity_ambiguous", "ENTITY_RESOLUTION", "CRITICAL", "Entity exposure is ambiguous"),
        ("low_coverage", "DATA_COVERAGE", "HIGH", "Evidence coverage is low"),
        (
            "high_redundancy",
            "FACTOR_REDUNDANCY",
            "HIGH",
            "Candidate may duplicate a baseline factor",
        ),
        (
            "memory_contradiction",
            "CONTRADICTING_EVIDENCE",
            "HIGH",
            "Research Memory contradicts the claim",
        ),
        ("single_regime", "REGIME_DEPENDENCE", "HIGH", "Result is supported in only one regime"),
        ("parameter_fragile", "PARAMETER_SENSITIVITY", "HIGH", "Result is parameter-sensitive"),
        (
            "negative_control_anomaly",
            "MODEL_RISK",
            "CRITICAL",
            "Negative control retained apparent power",
        ),
        ("missing_mechanism", "MECHANISM_SUPPORT", "HIGH", "Mechanism evidence is incomplete"),
    )
    result = []
    for key, category, severity, title in rules:
        if signals.get(key):
            result.append(
                {
                    "category": category,
                    "severity": severity,
                    "title": title,
                    "challenge": f"Mechanical safeguard `{key}` was triggered.",
                    "affected_claim": str(signals.get("claim", "research conclusion")),
                    "supporting_evidence": signals.get(f"{key}_evidence", []),
                    "contradicting_evidence": signals.get("supporting_evidence", []),
                    "falsification_condition": f"Resolve `{key}` with point-in-time evidence.",
                    "proposed_test": signals.get(f"{key}_test", "Run the bounded validation test."),
                    "resolution": {},
                    "status": "OPEN",
                    "confidence": 1.0,
                }
            )
    return result


def review_status(challenges: list[dict[str, Any]]) -> str:
    unresolved = [
        item for item in challenges if item["status"] not in {"RESOLVED", "ACCEPTED_RISK"}
    ]
    if any(item["severity"] == "CRITICAL" for item in unresolved):
        return "BLOCKED"
    if any(item["severity"] == "HIGH" for item in unresolved):
        return "NEEDS_EVIDENCE"
    return "QUALIFIED"


def resolve_challenge(challenge: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    if not evidence.get("test_id") or not evidence.get("result_checksum"):
        raise ValueError("resolution requires a referenced test and immutable result checksum")
    resolved = copy.deepcopy(challenge)
    resolved["resolution"] = evidence
    resolved["status"] = "RESOLVED"
    return resolved


def confidence_profile(components: dict[str, float]) -> dict[str, Any]:
    required = {
        "evidence_quality",
        "source_reliability",
        "data_coverage",
        "temporal_safety",
        "mechanism_support",
        "oos_robustness",
        "multiple_testing_survival",
        "independent_information",
        "regime_stability",
        "memory_consistency",
        "skeptic_risk",
        "scenario_robustness",
        "counterfactual_robustness",
    }
    normalized = {key: max(0.0, min(1.0, float(components.get(key, 0.0)))) for key in required}
    score = sum(normalized.values()) / len(normalized)
    classification = (
        "ROBUST" if score >= 0.75 else "MODERATELY_SENSITIVE" if score >= 0.5 else "FRAGILE"
    )
    return {
        "formula_version": "research-confidence-v1",
        "components": normalized,
        "summary_index": round(score, 6),
        "classification": classification,
        "semantics": "transparent_research_index_not_probability_or_profit_forecast",
    }


def transmission_value(kind: str, shock: float, parameters: dict[str, float]) -> float:
    weight = parameters.get("weight", 1.0)
    lag_discount = parameters.get("lag_discount", 1.0)
    raw = shock * weight * lag_discount
    if kind == "LINEAR":
        return raw
    if kind == "BOUNDED_LINEAR":
        bound = abs(parameters.get("bound", 1.0))
        return max(-bound, min(bound, raw))
    if kind == "THRESHOLD":
        threshold = abs(parameters.get("threshold", 0.0))
        return raw if abs(shock) >= threshold else 0.0
    if kind in {"LAGGED", "WEIGHTED_EXPOSURE", "CAPACITY_WEIGHTED", "LOCATION_WEIGHTED"}:
        return raw
    if kind == "BINARY_DISRUPTION":
        return weight if shock else 0.0
    raise ValueError(f"unsupported transmission function: {kind}")


def propagate_scenario(
    shocks: list[dict[str, Any]], edges: list[dict[str, Any]], *, max_depth: int = 4
) -> list[dict[str, Any]]:
    """Bounded, cycle-safe graph propagation through explicit supported relationships."""
    if not 1 <= max_depth <= 8:
        raise ValueError("max_depth must be between 1 and 8")
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        if edge.get("supported") and float(edge.get("confidence", 0.0)) > 0:
            adjacency.setdefault(str(edge["source"]), []).append(edge)
    outputs: list[dict[str, Any]] = []
    queue: deque[tuple[str, float, list[dict[str, Any]], int, str]] = deque(
        (str(s["target"]), float(s["value"]), [], 0, str(s["target"])) for s in shocks
    )
    visited: set[tuple[str, str]] = set()
    while queue:
        node, value, path, depth, origin = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in adjacency.get(node, []):
            target = str(edge["target"])
            marker = (origin, target)
            if marker in visited or target in [str(item.get("source")) for item in path]:
                continue
            visited.add(marker)
            parameters = {
                **edge.get("parameters", {}),
                "weight": float(edge.get("weight", 1.0)) * float(edge["confidence"]),
            }
            transmitted = transmission_value(str(edge.get("function", "LINEAR")), value, parameters)
            next_path = [
                *path,
                {
                    "source": node,
                    "target": target,
                    "relationship": edge.get("relationship"),
                    "confidence": edge["confidence"],
                    "function": edge.get("function", "LINEAR"),
                    "parameters": parameters,
                    "intermediate_value": transmitted,
                    "lag": edge.get("lag", 0),
                },
            ]
            outputs.append(
                {
                    "source_shock": origin,
                    "subject": target,
                    "value": transmitted,
                    "transmission_path": next_path,
                    "uncertainty_range": [transmitted * 0.8, transmitted * 1.2],
                }
            )
            queue.append((target, transmitted, next_path, depth + 1, origin))
    return outputs


def sensitivity_curve(
    shock_values: list[float], edges: list[dict[str, Any]], target: str
) -> dict[str, Any]:
    points = []
    for value in shock_values:
        impacts = propagate_scenario([{"target": edges[0]["source"], "value": value}], edges)
        matched = next((item for item in reversed(impacts) if item["subject"] == target), None)
        points.append({"shock": value, "response": matched["value"] if matched else None})
    numeric = [p["response"] for p in points if p["response"] is not None]
    monotonic = all(a <= b for a, b in zip(numeric, numeric[1:], strict=False))
    return {"points": points, "classification": "MONOTONIC" if monotonic else "UNSTABLE"}


def run_counterfactual(reference: dict[str, Any], intervention: dict[str, Any]) -> dict[str, Any]:
    state = copy.deepcopy(reference)
    operation = intervention["operation"]
    target = str(intervention["target"])
    if operation == "REMOVE_DRIVER":
        state.setdefault("drivers", {}).pop(target, None)
    elif operation == "SET_VALUE":
        state.setdefault("drivers", {})[target] = intervention["value"]
    elif operation == "REVERSE_CHANGE":
        state.setdefault("drivers", {})[target] = -float(state.get("drivers", {}).get(target, 0))
    elif operation == "NEUTRALIZE_EXPOSURE":
        state.setdefault("exposures", {})[target] = 0
    elif operation == "REMOVE_GRAPH_EDGE":
        state["edges"] = [edge for edge in state.get("edges", []) if edge.get("id") != target]
    elif operation == "REPLACE_ASSUMPTION":
        state.setdefault("assumptions", {})[target] = intervention["value"]
    elif operation == "REMOVE_FEATURE_COMPONENT":
        state.setdefault("features", {}).pop(target, None)
    else:
        raise ValueError(f"unsupported intervention: {operation}")
    return {
        "reference": reference,
        "counterfactual": state,
        "intervention": intervention,
        "changed": state != reference,
        "identification_status": "SIMULATED_MECHANISM",
        "semantics": "mechanism_conditioned_counterfactual_simulation_not_causal_effect",
        "checksum": digest({"reference": reference, "intervention": intervention, "state": state}),
    }


def alternative_explanation(
    candidate_increment: float, controlled_increment: float
) -> dict[str, Any]:
    collapsed = abs(controlled_increment) < max(0.01, abs(candidate_increment) * 0.2)
    return {
        "candidate_increment": candidate_increment,
        "controlled_increment": controlled_increment,
        "incremental_information_retained": not collapsed,
        "challenge_categories": ["ALTERNATIVE_EXPLANATION", "FACTOR_REDUNDANCY"]
        if collapsed
        else [],
    }
