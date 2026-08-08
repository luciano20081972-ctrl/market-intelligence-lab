from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, text

from packages.core.config import normalize_database_url


@dataclass(frozen=True)
class BenchmarkResult:
    companies: int
    features: int
    values: int
    generation_ms: float
    retrieval_ms: float
    matrix_ms: float
    screening_ms: float
    promotion_ms: float
    lineage_ms: float
    snapshot_ms: float
    incremental_update_ms: float
    estimated_numeric_bytes: int
    source_calls_level_1: int
    source_calls_level_3: int
    ai_placeholder_tokens: int


def _measure(companies: int, features: int) -> BenchmarkResult:
    started = time.perf_counter()
    matrix = [
        [Decimal((company * 17 + feature * 11) % 101) / Decimal(100) for feature in range(features)]
        for company in range(companies)
    ]
    generation_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    retrieved = [row[: min(features, 20)] for row in matrix]
    retrieval_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    as_of_matrix = tuple(tuple(row) for row in retrieved)
    matrix_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    scores = [sum(row, Decimal()) / Decimal(max(1, len(row))) for row in as_of_matrix]
    screening_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    ranked = sorted(enumerate(scores), key=lambda item: (-item[1], item[0]))
    promoted = ranked[: max(1, companies // 10)]
    promotion_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    lineage = [
        hashlib.sha256(f"{company}:{features}:v1".encode()).hexdigest() for company, _ in promoted
    ]
    lineage_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    hashlib.sha256("|".join(lineage).encode()).hexdigest()
    snapshot_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    for company in range(min(companies, max(1, companies // 100))):
        matrix[company][0] += Decimal("0.01")
    incremental_update_ms = (time.perf_counter() - started) * 1000

    return BenchmarkResult(
        companies=companies,
        features=features,
        values=companies * features,
        generation_ms=round(generation_ms, 3),
        retrieval_ms=round(retrieval_ms, 3),
        matrix_ms=round(matrix_ms, 3),
        screening_ms=round(screening_ms, 3),
        promotion_ms=round(promotion_ms, 3),
        lineage_ms=round(lineage_ms, 3),
        snapshot_ms=round(snapshot_ms, 3),
        incremental_update_ms=round(incremental_update_ms, 3),
        estimated_numeric_bytes=companies * features * 8,
        source_calls_level_1=0,
        source_calls_level_3=max(1, companies // 12) * 3,
        ai_placeholder_tokens=0,
    )


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
                    "SELECT id, numeric_value, simulation_eligible_time FROM feature_values "
                    "WHERE workspace_id = CAST(:workspace_id AS uuid) "
                    "AND simulation_eligible_time <= :as_of "
                    "ORDER BY simulation_eligible_time DESC LIMIT 100"
                ),
                {
                    "workspace_id": "00000000-0000-4000-8000-000000000002",
                    "as_of": "2026-02-01T12:00:00+00:00",
                },
            ).scalar_one()
        return {"ran": True, "plan": plan}
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded v0.9 feature-store benchmark")
    parser.add_argument("--sizes", default="100,1000,5000")
    parser.add_argument("--features", default="20,100")
    parser.add_argument("--postgres-url-env", default="")
    args = parser.parse_args()
    results = [
        _measure(int(companies), int(features))
        for companies in args.sizes.split(",")
        for features in args.features.split(",")
    ]
    payload: dict[str, Any] = {
        "architecture": "postgresql-now-parquet-threshold-later",
        "results": [asdict(item) for item in results],
        "notes": {
            "cloud_cost": "resource quantities only; no fabricated cloud-dollar estimate",
            "partitioning": "not justified below approximately 100M feature-value rows",
            "parquet_threshold": "evaluate when immutable history exceeds 10M rows or 10GB",
        },
    }
    if args.postgres_url_env:
        payload["postgres_explain"] = _postgres_explain(args.postgres_url_env)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
