from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any


def _milliseconds(started: float) -> float:
    return round((time.perf_counter() - started) * 1_000, 3)


def benchmark_sqlite(entity_count: int, relationship_count: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="mil-economic-graph-") as temporary:
        database = Path(temporary) / "graph.db"
        connection = sqlite3.connect(database)
        connection.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;
            CREATE TABLE entities (id INTEGER PRIMARY KEY, eligible INTEGER NOT NULL);
            CREATE TABLE relationships (
              id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL, object_id INTEGER NOT NULL,
              status TEXT NOT NULL, eligible INTEGER NOT NULL
            );
            CREATE TABLE evidence (id INTEGER PRIMARY KEY, relationship_id INTEGER NOT NULL);
            CREATE TABLE profiles (company_id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE relevance (company_id INTEGER NOT NULL, dataset_id TEXT NOT NULL,
              decision TEXT NOT NULL, PRIMARY KEY(company_id, dataset_id));
            CREATE INDEX ix_bench_outbound ON relationships(subject_id,status,eligible);
            CREATE INDEX ix_bench_inbound ON relationships(object_id,status,eligible);
            CREATE INDEX ix_bench_evidence ON evidence(relationship_id);
        """)
        started = time.perf_counter()
        connection.executemany(
            "INSERT INTO entities VALUES (?,1)", ((index,) for index in range(1, entity_count + 1))
        )
        connection.executemany(
            "INSERT INTO relationships VALUES (?,?,?,'verified',1)",
            (
                (
                    index,
                    ((index - 1) % entity_count) + 1,
                    (((index - 1) * 7919 + 104729) % entity_count) + 1,
                )
                for index in range(1, relationship_count + 1)
            ),
        )
        connection.executemany(
            "INSERT INTO evidence VALUES (?,?)",
            ((index, index) for index in range(1, relationship_count + 1)),
        )
        connection.execute("INSERT INTO profiles VALUES (1, ?)", (json.dumps({"version": 1}),))
        connection.executemany(
            "INSERT INTO relevance VALUES (1, ?, ?)",
            ((f"dataset-{index}", "PROCESS" if index < 4 else "IGNORE") for index in range(10)),
        )
        connection.commit()
        load_ms = _milliseconds(started)
        recursive = """
          WITH RECURSIVE walk(entity_id, depth, path) AS (
            SELECT 1, 0, ',1,'
            UNION ALL
            SELECT CASE WHEN r.subject_id=w.entity_id THEN r.object_id ELSE r.subject_id END,
                   w.depth+1,
                   w.path || CASE
                     WHEN r.subject_id=w.entity_id THEN r.object_id
                     ELSE r.subject_id END || ','
            FROM walk w JOIN relationships r
              ON (r.subject_id=w.entity_id OR r.object_id=w.entity_id)
            WHERE w.depth < ? AND r.status='verified' AND r.eligible<=1
              AND instr(w.path, ',' || CASE
                WHEN r.subject_id=w.entity_id THEN r.object_id
                ELSE r.subject_id END || ',')=0
          ) SELECT count(*) FROM (SELECT DISTINCT entity_id FROM walk LIMIT 500)
        """
        timings: dict[str, float] = {}
        for name, statement, params in (
            ("neighborhood_1_hop_ms", recursive, (1,)),
            ("traversal_2_hop_ms", recursive, (2,)),
            ("traversal_3_hop_ms", recursive, (3,)),
            ("as_of_traversal_ms", recursive, (3,)),
            ("driver_profile_ms", "SELECT payload FROM profiles WHERE company_id=?", (1,)),
            ("data_relevance_ms", "SELECT * FROM relevance WHERE company_id=?", (1,)),
            ("evidence_lookup_ms", "SELECT * FROM evidence WHERE relationship_id=?", (1,)),
        ):
            started = time.perf_counter()
            connection.execute(statement, params).fetchall()
            timings[name] = _milliseconds(started)
        plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM relationships "
            "WHERE subject_id=1 AND status='verified' AND eligible<=1"
        ).fetchall()
        footprint = database.stat().st_size
        connection.close()
    return {
        "engine": "sqlite",
        "entities": entity_count,
        "relationships": relationship_count,
        "load_ms": load_ms,
        "database_bytes": footprint,
        "indexed_plan": any("INDEX" in str(row) for row in plan),
        **timings,
    }


def benchmark_postgres(url: str, entity_count: int, relationship_count: int) -> dict[str, Any]:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TEMP TABLE bench_entities(id bigint PRIMARY KEY) ON COMMIT DROP")
        )
        connection.execute(text("""CREATE TEMP TABLE bench_relationships(
            id bigint PRIMARY KEY, subject_id bigint NOT NULL, object_id bigint NOT NULL,
            status text NOT NULL, eligible timestamptz NOT NULL) ON COMMIT DROP"""))
        connection.execute(
            text("INSERT INTO bench_entities SELECT generate_series(1,:count)"),
            {"count": entity_count},
        )
        connection.execute(text("""INSERT INTO bench_relationships
            SELECT value, ((value-1) % :entities)+1,
                   (((value-1)*7919+104729) % :entities)+1,
                   'verified', TIMESTAMPTZ '2026-01-01 00:00:00+00'
            FROM generate_series(1,:relationships) value"""), {
                "entities": entity_count, "relationships": relationship_count,
            })
        connection.execute(text("CREATE INDEX ON bench_relationships(subject_id,status,eligible)"))
        connection.execute(text("CREATE INDEX ON bench_relationships(object_id,status,eligible)"))
        connection.execute(text("ANALYZE bench_relationships"))
        plan = connection.execute(text("""EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            WITH RECURSIVE walk(entity_id,depth,path) AS (
              SELECT 1::bigint,0,ARRAY[1::bigint]
              UNION ALL
              SELECT CASE WHEN r.subject_id=w.entity_id THEN r.object_id ELSE r.subject_id END,
                     w.depth+1,
                     w.path || CASE
                       WHEN r.subject_id=w.entity_id THEN r.object_id
                       ELSE r.subject_id END
              FROM walk w JOIN bench_relationships r
                ON (r.subject_id=w.entity_id OR r.object_id=w.entity_id)
              WHERE w.depth<3 AND r.status='verified'
                AND r.eligible<=TIMESTAMPTZ '2026-01-02 00:00:00+00'
                AND NOT (CASE
                  WHEN r.subject_id=w.entity_id THEN r.object_id
                  ELSE r.subject_id END=ANY(w.path))
            ) SELECT * FROM walk LIMIT 500""")).scalar_one()
    engine.dispose()
    root = plan[0]
    return {
        "engine": "postgresql",
        "entities": entity_count,
        "relationships": relationship_count,
        "execution_ms": root["Execution Time"],
        "planning_ms": root["Planning Time"],
        "plan": root["Plan"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark bounded economic-graph queries")
    parser.add_argument("--sizes", nargs="+", default=["10000:50000"])
    parser.add_argument("--postgres-url-env")
    args = parser.parse_args()
    for size in args.sizes:
        entity_text, relationship_text = size.split(":", maxsplit=1)
        entities, relationships = int(entity_text), int(relationship_text)
        if entities <= 0 or relationships <= 0:
            raise SystemExit("benchmark sizes must be positive")
        print(json.dumps(benchmark_sqlite(entities, relationships), sort_keys=True))
        if args.postgres_url_env:
            url = os.getenv(args.postgres_url_env)
            if not url:
                raise SystemExit(f"{args.postgres_url_env} is not configured")
            print(json.dumps(benchmark_postgres(url, entities, relationships), sort_keys=True))


if __name__ == "__main__":
    main()
