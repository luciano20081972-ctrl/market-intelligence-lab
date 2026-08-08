# Reproducibility

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
