# Research-intelligence benchmark results

Run `python scripts/benchmark_research_intelligence.py` for indexed 10,000- and 100,000-memory workloads, 1,000 independence records, and 10,000 divergence events. It measures exact hypothesis, same-mechanism, known-failure, applicability, as-of, independence, and historical-analogue retrieval. Results are workstation observations, not service-level guarantees.

When `MIL_POSTGRES_TEST_DATABASE_URL` identifies an explicitly disposable PostgreSQL 17 database, the harness also verifies the major version and obtains `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` for the production exact-memory lookup without printing the URL. Never point this benchmark at staging or production.

Measured 2026-08-15 on the development workstation: at 10,000 / 100,000 memory entries, average exact lookup was 0.078 / 0.081 ms, same-mechanism lookup 0.172 / 1.102 ms, known-failure lookup 0.310 / 7.884 ms, applicability lookup 0.455 / 12.936 ms, and as-of retrieval 0.299 / 0.304 ms. Independence lookup was 0.081 / 0.079 ms and 10,000-event analogue lookup 0.114 / 0.105 ms. SQLite reported the intended index for every measured query. PostgreSQL EXPLAIN ANALYZE was not run locally because no explicitly disposable PostgreSQL URL was configured.
