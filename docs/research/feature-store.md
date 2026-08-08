# Point-in-time feature store

`FeatureDefinition` owns a stable key and scientific domain. Immutable versions define type, unit, frequency, lookback, computation and implementation versions, required datasets/graph drivers, Temporal Truth policy, missing-data and normalization policies, cost, and determinism. `FeatureValue` stores observation/effective/calculation/simulation-eligible clocks, value, unit, quality, checksums, job, normalization, and seed.

`get_feature_as_of` and `get_feature_matrix_as_of` expose only values with `simulation_eligible_time <= T` and observation time at or before T, using the universe version and memberships themselves eligible at T. Unsafe temporal quality never enters historical research. PostgreSQL is sufficient for beta point reads and moderate matrices; Parquet is the future dense-history layer.
