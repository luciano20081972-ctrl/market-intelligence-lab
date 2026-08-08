from __future__ import annotations

from collections.abc import Callable
from typing import Any

from packages.hypothesis.types import (
    ReasoningCandidate,
    ReasoningRequest,
    ResearchReasoningProvider,
)


class DeterministicReasoningProvider:
    name = "deterministic-fixture-v1"

    def available(self) -> bool:
        return True

    def generate_hypotheses(self, request: ReasoningRequest) -> list[ReasoningCandidate]:
        archetype = str(request.subject.get("archetype", "company")).lower()
        templates = {
            "semiconductor": (
                "Regional electricity-cost pressure may precede semiconductor margin changes",
                "Fabrication energy intensity creates a proposed transmission path from regional "
                "electricity prices through facility operating costs to company margins.",
                "weighted_regional_electricity_price_change_90d",
                ("eia.electricity.retail-price", "sec.companyfacts"),
                "negative",
            ),
            "airline": (
                "Jet-fuel and severe-weather exposure may affect airline operating margins",
                "Fuel consumption and disrupted flight networks form an evidence-backed "
                "relationship "
                "that may transmit energy and weather shocks to operating costs.",
                "route_weighted_fuel_weather_pressure_30d",
                ("eia.petroleum.jet-fuel", "noaa.weather", "sec.companyfacts"),
                "negative",
            ),
            "agriculture": (
                "Water stress and fertilizer-energy pressure may precede agricultural "
                "revenue changes",
                "Crop-region water availability and energy-intensive fertilizer costs form a "
                "proposed "
                "mechanism affecting yields and realized agricultural revenue.",
                "crop_region_water_energy_stress_120d",
                ("usda.crop-progress", "eia.natural-gas", "noaa.weather"),
                "negative",
            ),
        }
        title, rationale, feature_key, datasets, direction = templates.get(
            archetype,
            (
                "External operating-cost pressure may affect business outcomes",
                "Evidence-backed external drivers may transmit through operating inputs to "
                "measured "
                "business outcomes.",
                "external_cost_pressure_90d",
                tuple(request.datasets[:2]),
                "negative",
            ),
        )
        candidate = ReasoningCandidate(
            title=title,
            rationale=rationale,
            mechanism={
                "terminology": "hypothesized transmission path",
                "archetype": archetype,
                "graph_paths": list(request.graph_paths),
                "expected_direction": direction,
            },
            required_evidence=tuple(request.evidence),
            feature_specification={
                "feature_key": feature_key,
                "required_datasets": list(datasets),
                "required_graph_paths": list(request.graph_paths),
                "transformations": [
                    {"operation": "rolling_change", "window": 90},
                    {"operation": "zscore"},
                ],
                "aggregation": {"operation": "weighted_average", "weight": "exposure"},
                "lookback": 120,
                "lag": 1,
                "weighting": {"method": "graph_exposure"},
                "missing_data_policy": "mark_missing",
                "normalization": "cross_section_zscore_train_only",
                "expected_direction": direction,
                "required_output": "numeric",
                "temporal_policy": {
                    "simulation_eligible_only": True,
                    "normalization_fit_partition": "TRAIN",
                },
                "implementation_version": 1,
                "generator": self.name,
            },
            falsification_criteria=(
                "No persistent rank IC in final out-of-sample folds",
                "Adjusted p-value fails the configured multiple-testing threshold",
                "Candidate adds no information after conventional baselines",
            ),
        )
        return [candidate][: request.maximum_hypotheses]

    def critique_mechanism(self, mechanism: dict[str, Any]) -> list[str]:
        concerns = ["Relationship evidence does not establish causal proof"]
        if not mechanism.get("graph_paths"):
            concerns.append("No evidence-backed economic graph path was supplied")
        return concerns

    def suggest_required_evidence(self, mechanism: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"type": "supporting", "requirement": "point-in-time source evidence"},
            {"type": "contradicting", "requirement": "alternative mechanism evidence"},
        ]

    def suggest_feature_specification(self, mechanism: dict[str, Any]) -> dict[str, Any]:
        return self.generate_hypotheses(
            ReasoningRequest(
                subject={"archetype": mechanism.get("archetype", "company")},
                graph_paths=tuple(mechanism.get("graph_paths", ())),
                evidence=(),
                datasets=(),
                maximum_hypotheses=1,
            )
        )[0].feature_specification


class RuntimeModelReasoningProvider:
    """Provider-neutral adapter; the caller owns the bounded model transport."""

    name = "runtime-model-adapter"

    def __init__(
        self,
        invoke: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self._invoke = invoke

    def available(self) -> bool:
        return self._invoke is not None

    def _call(self, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._invoke is None:
            raise RuntimeError("runtime reasoning provider is unavailable")
        return self._invoke(capability, payload)

    def generate_hypotheses(self, request: ReasoningRequest) -> list[ReasoningCandidate]:
        response = self._call(
            "generate_hypotheses",
            {
                "subject": request.subject,
                "graph_paths": request.graph_paths,
                "evidence": request.evidence,
                "datasets": request.datasets,
                "maximum_hypotheses": request.maximum_hypotheses,
                "prohibited_capabilities": ["shell", "sql", "filesystem", "credentials"],
            },
        )
        candidates = response.get("candidates", [])
        if not isinstance(candidates, list):
            raise ValueError("runtime model returned an invalid candidate collection")
        return [ReasoningCandidate(**item) for item in candidates[: request.maximum_hypotheses]]

    def critique_mechanism(self, mechanism: dict[str, Any]) -> list[str]:
        return list(self._call("critique_mechanism", mechanism).get("concerns", []))

    def suggest_required_evidence(self, mechanism: dict[str, Any]) -> list[dict[str, Any]]:
        return list(self._call("suggest_required_evidence", mechanism).get("evidence", []))

    def suggest_feature_specification(self, mechanism: dict[str, Any]) -> dict[str, Any]:
        return dict(self._call("suggest_feature_specification", mechanism).get("specification", {}))


def unavailable_provider() -> ResearchReasoningProvider:
    return RuntimeModelReasoningProvider()
