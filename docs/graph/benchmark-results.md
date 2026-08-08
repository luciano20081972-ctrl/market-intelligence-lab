# Economic graph benchmark results

Measured on 2026-08-08 on the local Windows development host using Python 3.12 and SQLite with WAL. The topology has five deterministic outgoing relationships per entity and bounded cycle-aware recursive traversal. Times are single-run engineering measurements, not SLO guarantees.

| Shape | Load | 1 hop | 2 hops | 3 hops | As-of 3 hops | Profile | Relevance | Evidence | Footprint |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10K entities / 50K relationships | 318.453 ms | 0.463 ms | 0.279 ms | 0.859 ms | 0.759 ms | 0.034 ms | 0.044 ms | 0.028 ms | 4,714,496 bytes |
| 100K entities / 500K relationships | 12,092.411 ms | 0.760 ms | 0.518 ms | 1.058 ms | 0.870 ms | 0.054 ms | 0.051 ms | 0.042 ms | 50,266,112 bytes |

Both neighborhood plans used the outbound composite index. The production PostgreSQL job runs the 10K/50K benchmark with `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` in temporary tables after native migration/tests. A local PostgreSQL result was not produced because no disposable PostgreSQL service or test URL was available; staging/public databases are never used for destructive performance tests.

These results support retaining PostgreSQL for the bounded beta workload. They do not validate full-workspace or five-million-edge traversal, scenario propagation, or large graph algorithms. Reconsider materialized summaries or a specialized store only after representative PostgreSQL measurements miss an agreed SLO after indexing and bounded-query tuning.
