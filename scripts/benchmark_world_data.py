from __future__ import annotations

import argparse
import sqlite3
import tempfile
import time
from pathlib import Path


def elapsed(started: float) -> float:
    return round(time.perf_counter() - started, 4)


def benchmark(row_count: int) -> dict[str, float | int]:
    with tempfile.TemporaryDirectory(prefix="mil-world-data-") as temporary:
        database = Path(temporary) / "benchmark.db"
        connection = sqlite3.connect(database)
        connection.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE observations (
              id INTEGER PRIMARY KEY, series_id INTEGER NOT NULL,
              observation_time INTEGER NOT NULL, revision_time INTEGER NOT NULL,
              simulation_eligible_time INTEGER NOT NULL, value REAL NOT NULL,
              manifest_id INTEGER NOT NULL
            );
            CREATE INDEX ix_benchmark_as_of ON observations
              (series_id, observation_time, simulation_eligible_time, revision_time);
            CREATE INDEX ix_benchmark_manifest ON observations (manifest_id);
        """)
        batch = 10_000
        started = time.perf_counter()
        for offset in range(0, row_count, batch):
            stop = min(offset + batch, row_count)
            connection.executemany(
                "INSERT INTO observations VALUES (?,?,?,?,?,?,?)",
                (
                    (index, index % 100, index // 10, index, index, index / 100, index % 1000)
                    for index in range(offset, stop)
                ),
            )
        connection.commit()
        insert_seconds = elapsed(started)

        started = time.perf_counter()
        connection.execute(
            "SELECT observation_time, max(revision_time) FROM observations "
            "WHERE series_id=? AND simulation_eligible_time<=? GROUP BY observation_time",
            (42, row_count // 2),
        ).fetchall()
        as_of_seconds = elapsed(started)

        started = time.perf_counter()
        connection.execute(
            "SELECT * FROM observations WHERE series_id=? AND observation_time BETWEEN ? AND ?",
            (42, row_count // 4, row_count // 2),
        ).fetchall()
        range_seconds = elapsed(started)

        started = time.perf_counter()
        connection.execute(
            "SELECT count(*) FROM observations WHERE manifest_id=?", (42,)
        ).fetchone()
        manifest_seconds = elapsed(started)
        footprint = database.stat().st_size
        plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM observations WHERE series_id=? "
            "AND observation_time BETWEEN ? AND ?",
            (42, 0, row_count),
        ).fetchall()
        connection.close()
    return {
        "rows": row_count,
        "insert_seconds": insert_seconds,
        "as_of_seconds": as_of_seconds,
        "range_seconds": range_seconds,
        "manifest_seconds": manifest_seconds,
        "bytes": footprint,
        "range_plan_uses_index": int(any("INDEX" in str(item) for item in plan)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure temporal observation access patterns")
    parser.add_argument("--rows", type=int, nargs="+", default=[100_000, 1_000_000])
    args = parser.parse_args()
    for count in args.rows:
        if count <= 0:
            raise SystemExit("row count must be positive")
        print(benchmark(count))


if __name__ == "__main__":
    main()
