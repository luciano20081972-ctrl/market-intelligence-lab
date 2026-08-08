# Roadmap

## World-intelligence release sequence (proposed 2026-08-07)

Effort uses focused engineer-weeks and assumes one experienced developer with Codex assistance. Runtime ranges are directional and must be replaced by measured benchmarks. Every release preserves the no-broker/no-real-money boundary.

### v0.7 — Temporal Truth and high-density world-data foundation

**Status: implemented on the v0.7 feature branch.** Live provider verification and object-storage cloud adapters remain operational follow-ups, not hidden release claims.

- **Scope:** canonical temporal envelope and eligibility policies; immutable source/object manifests; point-in-time query/test harness; SEC bulk submissions/companyfacts; FRED/ALFRED; one agency pilot (EIA recommended); distributed budget/watermark extensions to existing jobs; bounded live rehearsals.
- **Reuse:** existing providers/jobs/provenance/migrations; SEC APIs, EdgarTools parser, FRED/ALFRED and EIA APIs.
- **Build:** temporal policy registry, revision model, object references, source manifests, point-in-time fixtures and feature-input contract.
- **Risks:** ambiguous historical availability, amendments/revisions, source terms, entity mapping, storage growth.
- **Effort / Codex:** 8-12 engineer-weeks; high schema/migration/test workload, medium adapter workload.
- **Runtime:** low-medium; 8-16 vCPU batch, 32-64 GB RAM, 0.2-1 TB object tier for a 100-company pilot.
- **Beta value:** trustworthy “what was knowable when” financial/macro/energy evidence.

### v0.8 — Economic entity/driver graph and relevance router

- **Scope:** typed relational graph, evidence/versioned edges, identifiers, bounded recursive queries, driver profiles, routing budgets/exploration, dossier skeleton.
- **Reuse:** PostgreSQL/RLS/provenance; pgvector optional; NetworkX for offline algorithms; PostGIS only if the first spatial pilot requires it.
- **Build:** entity/edge/evidence schemas, identity workflows, graph SLO benchmark, routing policy and benchmark set.
- **Risks:** false entity links, edge confidence, graph explosion, prior bias, weak driver ground truth.
- **Effort / Codex:** 10-14 weeks; high domain/test/UI workload.
- **Runtime:** medium; graph materializations and incremental scoring, no dedicated graph database.
- **Beta value:** explainable, different driver sets per company and selective source execution.

### v0.9 — Progressive resolution and point-in-time feature store

- **Scope:** L0-L4 universe policies, reproducible promotions, point-in-time feature definitions/materializations, budgets/cost ledger, first sector-specific sources.
- **Reuse:** pandas/Arrow/Parquet ecosystem, existing backtests, agency bulk/API data.
- **Build:** feature registry/lineage, as-of joins, promotion service, cost/coverage dashboard.
- **Risks:** feature leakage, expensive recomputation, selection bias, universe survivorship.
- **Effort / Codex:** 10-16 weeks; high data/benchmark workload.
- **Runtime:** medium-high; columnar/object storage and parallel batch workers become mandatory near 1,000 companies.
- **Beta value:** thousands screened cheaply while deep research stays bounded.

### v0.10 — Hypothesis Factory with Qlib/RD-Agent evaluation

- **Scope:** machine-readable hypotheses, experiment families/gates, walk-forward/robustness pipeline; Qlib optional engine; sandboxed RD-Agent benchmark, not autonomous production coding.
- **Reuse:** Qlib, RD-Agent patterns/optional runner, existing simulation and leakage rules.
- **Build:** experiment control plane, manifests, statistical/multiplicity gates, sandbox and result normalization.
- **Risks:** multiple testing, agent hallucination, non-reproducible generated code, model/provider cost.
- **Effort / Codex:** 12-18 weeks; high research/evaluation workload.
- **Runtime:** high and bursty; CPU/GPU experiment pools and bounded hosted-model batches.
- **Beta value:** falsifiable driver hypotheses that cannot bypass quantitative gates.

### v0.11 — Research Memory, divergence, and signal independence

- **Scope:** durable positive/negative experiment memory, duplicate detection, outcome links, divergence events, Independent Information Score.
- **Reuse:** PostgreSQL/object store/pgvector, QuantStats/skfolio adapters, NetworkX exports.
- **Build:** memory schemas/retrieval evaluation, source-dependency graph, divergence baselines, conditional contribution tests.
- **Risks:** retrospective narrative, correlation mistaken for independence, embedding retrieval omissions.
- **Effort / Codex:** 10-14 weeks; medium-high analytics/UI workload.
- **Runtime:** medium-high; vector/relational retrieval and scheduled cross-source comparisons.
- **Beta value:** institutional learning, fewer duplicate tests, orthogonal-signal prioritization.

### v0.12 — Skeptic agent and scenario/counterfactual engine

- **Scope:** blocking red-team findings, scenario versioning/propagation, bounded sensitivities, thesis-failure counterfactuals.
- **Reuse:** graph/router/research memory, quantitative libraries, runtime AI gateway.
- **Build:** skeptic test catalog, approval workflow, propagation levels, calibration/replay suite.
- **Risks:** false causal paths, correlated shocks, invented precision, waived findings.
- **Effort / Codex:** 10-16 weeks; high evaluation and UX workload.
- **Runtime:** medium; asynchronous graph propagation and selective reasoning.
- **Beta value:** explicit challenge process and portfolio-wide exposure exploration.

### v0.13 — Feedback/calibration and portfolio/risk integration

- **Scope:** forecast distributions/outcomes, calibration and attribution, reliability updates, information-value routing, integration with skfolio/risk and optional advanced engine comparisons.
- **Reuse:** skfolio, QuantStats, internal paper/risk/backtest, optional LEAN/Nautilus after approval.
- **Build:** outcome scheduler, calibration dashboards, guarded policy updates, portfolio-level constraints.
- **Risks:** attribution ambiguity, feedback loops, regime drift, optimizer instability.
- **Effort / Codex:** 10-14 weeks; high statistical/test workload.
- **Runtime:** medium-high; scheduled evaluation/retraining and portfolio simulations.
- **Beta value:** measured learning and calibrated research confidence rather than anecdotal wins.

### v0.14 — Private-beta hardening

- **Scope:** workspace-aware RLS, security/license/privacy review, backups/restore, SLOs, observability, cost controls, source degradation, runbooks and selected live validations.
- **Reuse:** current security/CI/observability foundations and managed PostgreSQL/object storage.
- **Build:** operations automation, policy evidence, load/chaos/recovery tests, admin controls.
- **Risks:** provider rights, operational complexity, cost spikes, tenant isolation.
- **Effort / Codex:** 10-16 weeks; medium feature, high verification/documentation workload.
- **Runtime:** production-like multi-worker environment; measured capacity targets.
- **Beta value:** safe invited-user operation with honest source and model health.

### v1.0 — Validated research platform

- **Scope:** frozen supported source/engine matrix, benchmark evidence, calibration/limitations report, security/data-license sign-off, performance budgets, reproducible release.
- **Reuse:** all approved adapters and platform foundations.
- **Build:** final gaps revealed by beta evidence, migration/support policies, release documentation.
- **Risks:** scientific validity and user interpretation remain larger than software completeness.
- **Effort / Codex:** 8-14 weeks after beta findings; verification-heavy.
- **Runtime:** sized from v0.14 measurements, not roadmap estimates.
- **Beta value:** a validated entity-specific research platform, not a promise of profitable prediction.

Ordering is dependency-driven: trustworthy time precedes graphs/features; graphs and routing precede expensive research; experiments precede memory/independence; all precede feedback and beta hardening.

## Completed foundation

- **v0.1-v0.4:** modular API/UI, provenance-complete market data, deterministic backtests/paper simulation, operational historical ingestion, workers/schedules/observability.
- **v0.5:** secure multi-user foundation, workspace controls, provider/infrastructure governance.
- **v0.6:** upstream license governance, normalized SEC entities, analytics/optimization boundaries, and optional LEAN contracts. Fixture verification never means live production readiness.

## Controlling research

See [world-intelligence architecture](architecture/world-intelligence.md), [high-density data sources](research/high-density-data-sources.md), [open-source capability audit](research/open-source-capability-audit.md), and [build-versus-integrate matrix](research/build-vs-integrate-matrix.md).
