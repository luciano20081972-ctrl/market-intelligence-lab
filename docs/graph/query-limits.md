# Graph query limits

Graph APIs use workspace-scoped bounded traversal. The default depth is 3, maximum depth is 5, default node budget is 100, maximum node budget is 500, and timeout is configurable from 10 to 5,000 milliseconds. Traversal prevents cycles by carrying the visited entity path and returns deterministic ordering.

PostgreSQL executes the production recursive CTE. SQLite uses a behaviorally equivalent bounded breadth-first traversal for deterministic local tests. Both enforce entity/relationship validity and `simulation_eligible_time <= as_of`, so a historical request cannot expose a later discovery.

Clients should expand progressively rather than rendering an entire workspace graph. An exceeded node/time budget returns an explicit error; it never falls back to an unbounded query. Evidence expansion is performed only for returned relationship paths.

Run the beta benchmark with `python scripts/benchmark_economic_graph.py --sizes 10000:50000`. Add `100000:500000` when resources permit. Supplying `--postgres-url-env MIL_POSTGRES_TEST_DATABASE_URL` runs an isolated temporary-table PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` without printing the URL.

The latest measured local results are recorded in [benchmark-results.md](benchmark-results.md).
