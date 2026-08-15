from __future__ import annotations

import json
import time
from collections.abc import Callable

from packages.adversarial_intelligence.service import (
    confidence_profile,
    generate_challenges,
    propagate_scenario,
    run_counterfactual,
)


def timed(name: str, count: int, operation: Callable[[], object]) -> dict[str, float | int | str]:
    started = time.perf_counter()
    for _ in range(count):
        operation()
    elapsed = time.perf_counter() - started
    return {
        "name": name,
        "count": count,
        "seconds": round(elapsed, 6),
        "ops_per_second": round(count / max(elapsed, 1e-9), 2),
    }


def main() -> None:
    edges = [
        {
            "source": "driver",
            "target": "facility",
            "supported": True,
            "confidence": 0.9,
            "weight": 0.5,
            "function": "WEIGHTED_EXPOSURE",
        },
        {
            "source": "facility",
            "target": "company",
            "supported": True,
            "confidence": 0.8,
            "weight": 0.7,
            "function": "CAPACITY_WEIGHTED",
        },
    ]
    components = {
        key: 0.7
        for key in (
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
        )
    }
    results = [
        timed(
            "challenge_generation",
            1_000,
            lambda: generate_challenges({"low_coverage": True, "single_regime": True}),
        ),
        timed(
            "bounded_graph_propagation",
            1_000,
            lambda: propagate_scenario([{"target": "driver", "value": 0.2}], edges, max_depth=4),
        ),
        timed(
            "counterfactual_execution",
            1_000,
            lambda: run_counterfactual(
                {"drivers": {"driver": 0.2}}, {"operation": "REMOVE_DRIVER", "target": "driver"}
            ),
        ),
        timed("confidence_calculation", 1_000, lambda: confidence_profile(components)),
    ]
    print(json.dumps({"bounded_graph_depth": 4, "results": results}, indent=2))


if __name__ == "__main__":
    main()
