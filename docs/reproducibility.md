# Reproducibility

v0.9 `FeatureSnapshot` is the research reproducibility boundary. It captures the eligible universe version, ordered feature-set version, entity and feature-value identities, as-of time, application SHA, migration head, source/graph/routing/policy references, seeds, warnings, and a canonical checksum. `ResearchScreeningRun` adds decomposed decisions, budget usage, reason distribution, and its own checksum. Re-running identical software, configuration, and point-in-time inputs returns the same snapshot and screening run; revisions append values rather than rewriting history.

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
