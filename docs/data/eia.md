# EIA retail electricity price pilot

The v0.7 EIA pilot deliberately targets the official monthly retail electricity price dataset. It was selected because it has a compact, interpretable value, stable units, explicit monthly periods, and useful geographic facets, making it a strong test of non-market temporal normalization without opening a broad agency ingestion surface.

The direct EIA v2 JSON adapter preserves series metadata, frequency, geography, units, raw source value, observation month, retrieval time, manifest, checksum, and quality flags. Because a historical per-row publication timestamp is not consistently present, retrieval time is the conservative publication/revision/eligibility floor. This limitation is shown rather than guessed away.

Incremental jobs persist a dataset cursor and are idempotent on series, observation period/value, and manifest checksum. `MIL_EIA_API_KEY` is backend-only. Live verification is opt-in; fixtures preserve units, geography, missing values, and month precision.
