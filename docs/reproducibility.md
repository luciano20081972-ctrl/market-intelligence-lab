# Reproducibility

v0.10 extends the v0.9 `FeatureSnapshot` boundary with an immutable `ExperimentManifest`: hypothesis/specification versions, outcome, universe and graph/reference state, source manifests, application SHA, Alembic head, dependency versions, validation protocol, seed, exact partitions, engine configuration, warnings, and canonical checksums. Every fold, failed variant, correction, control, and promotion decision is retained. Re-running identical software, configuration, and point-in-time inputs returns the same deterministic fixture artifacts; revisions append rather than rewriting history.

Backtests retain canonical manifests and validation reports. v0.6 extends the same discipline:

- SEC filings retain accession, CIK, acceptance/retrieval/reporting timestamps, source URL,
  content checksum, raw reference, parser version, EdgarTools version, and amendment state.
- Analytics comparisons retain the input return-series checksum, aligned period/benchmark,
  both metric engines, differences, tolerances, methodology notes, and agreement status.
- Optimization experiments retain universe, input checksum, estimator configuration,
  constraints, train/validation periods, weights, objective/risk values, optimizer version,
  random seed, warnings, and failure reason.
- External engine runs retain normalized request/result manifests, engine version/commit,
  fees/slippage assumptions, comparison explanation, and resource-limit intent.

Ordinary tests use deterministic fixtures and make no network calls. Random seeds are explicit.
Raw filings, generated reports, caches, and external-engine artifacts are not committed.
# World-data reproducibility

Every acquisition is identified by its SHA-256 checksum, immutable logical raw-object key, parser/schema version, retrieval and coverage times, accepted/rejected counts, license identifier, optional parent manifest, and job. Replaying a normalized dataset begins from the referenced raw bytes and manifest; as-of research additionally records the UTC cutoff and selects only rows whose simulation eligibility is not later than that cutoff.
