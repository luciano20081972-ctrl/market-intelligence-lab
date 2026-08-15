"""Bounded v0.11 research-intelligence lookup benchmark.

SQLite provides a safe local measurement. Set the named environment variable only
to an explicitly disposable PostgreSQL 17 database to obtain EXPLAIN ANALYZE plans.
The URL itself is never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text


def benchmark_sqlite(memory_count: int, divergence_count: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temporary:
        connection = sqlite3.connect(Path(temporary) / "research-intelligence.db")
        connection.executescript("""
        CREATE TABLE memory(workspace TEXT, hypothesis TEXT, mechanism TEXT, feature TEXT,
          outcome TEXT, conclusion TEXT, sector TEXT, business_model TEXT, eligible INTEGER);
        CREATE INDEX ix_memory_exact ON memory(workspace, hypothesis);
        CREATE INDEX ix_memory_mechanism ON memory(workspace, mechanism, feature, outcome);
        CREATE INDEX ix_memory_failure ON memory(workspace, conclusion, feature, outcome);
        CREATE INDEX ix_memory_applicability ON memory(workspace, sector, business_model);
        CREATE INDEX ix_memory_asof ON memory(workspace, eligible);
        CREATE TABLE divergence(workspace TEXT, entity TEXT, magnitude REAL, eligible INTEGER);
        CREATE INDEX ix_divergence_asof ON divergence(workspace, entity, eligible);
        CREATE TABLE independence(workspace TEXT, factor TEXT, score REAL);
        CREATE INDEX ix_independence_factor ON independence(workspace, factor);
        """)
        workspace = "benchmark-workspace"
        connection.executemany(
            "INSERT INTO memory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    workspace,
                    f"h-{index}",
                    f"m-{index % 250}",
                    f"f-{index % 50}",
                    "forward-return",
                    "NEGATIVE" if index % 4 == 0 else "POSITIVE",
                    f"sector-{index % 12}",
                    f"model-{index % 20}",
                    index,
                )
                for index in range(memory_count)
            ),
        )
        connection.executemany(
            "INSERT INTO divergence VALUES (?, ?, ?, ?)",
            (
                (workspace, f"entity-{index % 100}", (index % 100) / 100, index)
                for index in range(divergence_count)
            ),
        )
        connection.executemany(
            "INSERT INTO independence VALUES (?, ?, ?)",
            ((workspace, f"factor-{index}", (index % 100) / 100) for index in range(1_000)),
        )
        connection.commit()
        queries = {
            "exact_hypothesis": (
                "SELECT * FROM memory WHERE workspace=? AND hypothesis=?",
                (workspace, f"h-{memory_count // 2}"),
            ),
            "same_mechanism": (
                "SELECT * FROM memory WHERE workspace=? AND mechanism=? "
                "AND feature=? AND outcome=?",
                (workspace, "m-10", "f-10", "forward-return"),
            ),
            "known_failure": (
                "SELECT * FROM memory WHERE workspace=? AND conclusion='NEGATIVE' "
                "AND feature=? AND outcome=?",
                (workspace, "f-0", "forward-return"),
            ),
            "applicability": (
                "SELECT * FROM memory WHERE workspace=? AND sector=? AND business_model=?",
                (workspace, "sector-2", "model-10"),
            ),
            "memory_as_of": (
                "SELECT * FROM memory WHERE workspace=? AND eligible<=? "
                "ORDER BY eligible DESC LIMIT 100",
                (workspace, memory_count // 2),
            ),
            "independence": (
                "SELECT * FROM independence WHERE workspace=? AND factor=?",
                (workspace, "factor-500"),
            ),
            "divergence_analogues": (
                "SELECT * FROM divergence WHERE workspace=? AND entity=? AND eligible<=? "
                "ORDER BY eligible DESC LIMIT 20",
                (workspace, "entity-10", divergence_count),
            ),
        }
        timings: dict[str, float] = {}
        plans: dict[str, list[str]] = {}
        for name, (statement, parameters) in queries.items():
            started = time.perf_counter()
            for _ in range(100):
                connection.execute(statement, parameters).fetchall()
            timings[name] = round((time.perf_counter() - started) * 10, 3)
            plans[name] = [
                row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + statement, parameters)
            ]
        connection.close()
        return {
            "memory_entries": memory_count,
            "divergence_events": divergence_count,
            "average_ms": timings,
            "plans": plans,
        }


def explain_postgres(url: str) -> dict[str, Any]:
    engine = create_engine(url)
    with engine.connect() as connection:
        major = int(str(connection.scalar(text("SHOW server_version_num")))[:2])
        if major != 17:
            raise RuntimeError("disposable benchmark database must run PostgreSQL 17")
        plan = connection.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            SELECT id FROM research_memory_entries
            WHERE workspace_id = :workspace AND hypothesis_checksum = :checksum
        """),
            {"workspace": uuid.UUID(int=0), "checksum": "benchmark"},
        ).scalar_one()
    engine.dispose()
    return {"postgres_major": major, "exact_lookup_plan": plan}


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded v0.11 research-intelligence benchmark")
    parser.add_argument("--memory", nargs="+", type=int, default=[10_000, 100_000])
    parser.add_argument("--divergence", type=int, default=10_000)
    parser.add_argument("--postgres-url-env", default="MIL_POSTGRES_TEST_DATABASE_URL")
    args = parser.parse_args()
    for count in args.memory:
        print(json.dumps(benchmark_sqlite(count, args.divergence), sort_keys=True))
    url = os.getenv(args.postgres_url_env)
    if url:
        print(json.dumps(explain_postgres(url), sort_keys=True, default=str))


if __name__ == "__main__":
    main()
