from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from sqlalchemy import create_engine, text

from packages.core.config import normalize_database_url


@dataclass(frozen=True)
class BenchmarkResult:
    hypotheses: int
    experiments: int
    folds: int
    deduplication_ms: float
    experiment_retrieval_ms: float
    fold_retrieval_ms: float
    statistics_aggregation_ms: float
    promotion_evaluation_ms: float
    manifest_retrieval_ms: float


def _measure(hypotheses: int, experiments: int, folds: int) -> BenchmarkResult:
    hypothesis_rows: list[dict[str, Any]] = [
        {
            "id": index,
            "semantic_key": hashlib.sha256(f"driver:{index % hypotheses}:v1".encode()).hexdigest(),
        }
        for index in range(hypotheses)
    ]
    experiment_rows: list[dict[str, Any]] = [
        {"id": index, "hypothesis_id": index % hypotheses, "status": "COMPLETED"}
        for index in range(experiments)
    ]
    fold_rows: list[dict[str, Any]] = [
        {
            "id": index,
            "experiment_id": index % experiments,
            "rank_ic": ((index * 17) % 101 - 50) / 1000,
        }
        for index in range(folds)
    ]
    manifests: dict[int, dict[str, str]] = {
        int(item["id"]): {"checksum": f"manifest-{item['id']}"} for item in experiment_rows
    }

    started = time.perf_counter()
    unique = {item["semantic_key"] for item in hypothesis_rows}
    assert len(unique) == hypotheses
    deduplication_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    experiment_index: dict[int, list[dict[str, Any]]] = {}
    for item in experiment_rows:
        experiment_index.setdefault(int(item["hypothesis_id"]), []).append(item)
    _ = experiment_index[hypotheses // 2]
    experiment_retrieval_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    fold_index: dict[int, list[dict[str, Any]]] = {}
    for item in fold_rows:
        fold_index.setdefault(int(item["experiment_id"]), []).append(item)
    _ = fold_index[experiments // 2]
    fold_retrieval_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    values = np.asarray([item["rank_ic"] for item in fold_rows], dtype=float)
    _ = (float(values.mean()), float(values.std()), float(np.mean(values > 0)))
    statistics_aggregation_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    gates = [item for item in experiment_rows if item["status"] == "COMPLETED"]
    _ = sum(1 for item in gates if fold_index.get(int(item["id"])))
    promotion_evaluation_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    _ = [manifests[index] for index in range(min(1000, experiments))]
    manifest_retrieval_ms = (time.perf_counter() - started) * 1000

    return BenchmarkResult(
        hypotheses=hypotheses,
        experiments=experiments,
        folds=folds,
        deduplication_ms=round(deduplication_ms, 3),
        experiment_retrieval_ms=round(experiment_retrieval_ms, 3),
        fold_retrieval_ms=round(fold_retrieval_ms, 3),
        statistics_aggregation_ms=round(statistics_aggregation_ms, 3),
        promotion_evaluation_ms=round(promotion_evaluation_ms, 3),
        manifest_retrieval_ms=round(manifest_retrieval_ms, 3),
    )


def _resource_requirements(companies: int) -> dict[str, int]:
    hypotheses = companies * 10
    experiments = hypotheses * 3
    folds = experiments * 5
    return {
        "companies": companies,
        "maximum_hypotheses": hypotheses,
        "candidate_features": hypotheses,
        "experiments_with_robustness_variants": experiments,
        "walk_forward_folds": folds,
        "runtime_model_requests_default": 0,
        "runtime_model_requests_if_enabled": companies * 2,
        "estimated_tokens_default": 0,
        "estimated_compute_seconds_fixture": round(folds * 0.002),
    }


def _postgres_explain(environment_name: str) -> dict[str, Any] | None:
    url = os.getenv(environment_name)
    if not url:
        return None
    engine = create_engine(normalize_database_url(url))
    try:
        with engine.connect() as connection:
            plan = connection.execute(
                text(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
                    "SELECT e.id, e.status, count(f.id) AS fold_count "
                    "FROM factor_experiments e "
                    "LEFT JOIN factor_experiment_folds f ON f.experiment_id = e.id "
                    "WHERE e.workspace_id = CAST(:workspace_id AS uuid) "
                    "GROUP BY e.id, e.status ORDER BY e.created_at DESC LIMIT 100"
                ),
                {"workspace_id": "00000000-0000-4000-8000-000000000002"},
            ).scalar_one()
        return {"ran": True, "plan": plan}
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded v0.10 hypothesis research benchmark")
    parser.add_argument("--postgres-url-env", default="")
    args = parser.parse_args()
    payload: dict[str, Any] = {
        "results": [asdict(_measure(100, 1000, 10_000))],
        "deep_research_resource_requirements": [
            _resource_requirements(companies) for companies in (10, 50, 100)
        ],
        "notes": {
            "costs": "resource quantities only; no unsupported dollar estimates",
            "ordinary_runtime_reasoning": "disabled",
            "hypothesis_limit_per_company": 10,
        },
    }
    if args.postgres_url_env:
        payload["postgres_explain"] = _postgres_explain(args.postgres_url_env)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
