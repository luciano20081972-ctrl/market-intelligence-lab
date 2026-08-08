# Safe feature DSL

Canonical candidate features are declarative. Allowed operations are `lag`, `difference`, `ratio`, `rolling_mean`, `rolling_std`, `rolling_change`, `weighted_average`, `zscore`, `percentile`, `rank`, `winsorize`, and `cross_section_rank`. Validation enforces known operations, input/output types, bounded lookbacks/lags, parameter ranges, missing-data policy, normalization, weighting, and temporal safety before materialization. Arbitrary Python is not accepted by the API or stored as a canonical definition.

If experimental generated code is added later, it must run in an isolated secret-free process with bounded resources, timeout, deterministic inputs, artifact capture, restricted filesystem, and network disabled by default.
