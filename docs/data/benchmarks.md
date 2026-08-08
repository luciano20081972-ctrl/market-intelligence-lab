# Temporal observation benchmarks

Run `python scripts/benchmark_world_data.py --rows 100000 1000000` to measure batched inserts, one as-of grouping, a series range read, a manifest lookup, SQLite footprint, and query-plan index use. Results are workstation observations, not service-level guarantees. PostgreSQL 17 must be measured independently in a disposable environment before production sizing.

The schema indexes are based on these access paths rather than speculative single-column coverage: macro as-of reads use `(series_id, observation_time, simulation_eligible_time)`, energy ranges use `(series_id, observation_time)`, and manifest references are indexed. The release report records the exact local measurements.

## 2026-08-07 local SQLite measurement

| Rows | Batched insert | As-of | Range | Manifest | Footprint | Range index |
|---:|---:|---:|---:|---:|---:|---|
| 100,000 | 0.7188 s | 0.0010 s | 0.0001 s | <0.0001 s | 6,774,784 B | used |
| 1,000,000 | 33.8450 s | 0.0061 s | 0.0001 s | 0.0001 s | 70,066,176 B | used |

The run used a disposable SQLite database on the release workstation. It does not substitute for the unavailable disposable PostgreSQL 17 run.
