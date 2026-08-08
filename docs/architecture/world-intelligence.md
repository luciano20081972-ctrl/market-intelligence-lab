# World-intelligence architecture

Status: design proposal for v0.7+, 2026-08-07. This document does not authorize production implementation.

## Product thesis

Market Intelligence Lab should discover the company-specific variables that affect economic performance, test those relationships without look-ahead, and retain what it learns. It is not a universal-factor stock predictor and it is not an LLM that repeatedly browses the public web.

```text
high-density sources -> immutable landing records -> Temporal Truth
  -> normalized entities and exposures -> feature store -> relevance router
  -> hypotheses -> quantitative validation -> research memory
  -> current evidence, divergence, and scenarios
```

AI sees bounded evidence packets selected from durable structured data. Deterministic services own ingestion, identity, time, feature computation, tests, and state transitions. Statistical engines—not model prose—decide whether evidence passes research gates.

## Current-system audit

The audit covers tracked code, migrations, tests, infrastructure, and user-facing workflows at v0.6.0 (`4cf7d994a1827412f05740d2ed0231ce4ba57e67`). No working component is removed by this proposal.

| Area | What exists | Decision | Direction |
|---|---|---|---|
| Market data | Normalized bars, actions, calendars, quality/reconciliation, Stooq/Twelve Data/synthetic adapters | EXTEND | Preserve contracts; add source-specific temporal metadata and columnar cold storage. |
| Provider framework | Typed capabilities, registry, health, provenance, fixed-host adapters | KEEP | Generalize into source manifests and ingestion contracts. |
| SEC intelligence | Normalized entities/filings/facts, fixture-first EdgarTools boundary | EXTEND | Make EdgarTools a pinned adapter; add bulk submissions/companyfacts and point-in-time XBRL facts. |
| Authentication | Supabase JWT/JWKS verification and internal profiles | KEEP | Keep auth provider outside domain models; add service identities for workers. |
| Workspace isolation | Membership/RBAC, tenant guards, deny-by-default RLS | EXTEND | Add workspace-aware PostgreSQL policies before multi-tenant beta. |
| Auditing | Application audit events | EXTEND | Add append-only research decisions, model calls, dataset versions, and evidence hashes. |
| Backtesting | Deterministic internal bar simulator, manifests, friction and metrics | WRAP | Retain as conformance oracle; expose engine protocol and compare optional LEAN/Nautilus runs. |
| Paper trading | Database-only simulated orders, positions, risk limits | KEEP | Retain no-broker boundary; require skeptic gates before `paper-active`. |
| Portfolio analytics | Internal deterministic metrics plus QuantStats compatibility adapter | REPLACE | Keep canonical metric schema; call real pinned QuantStats behind reconciliation. |
| Optimization | Internal constrained optimizer plus skfolio compatibility adapter | REPLACE | Keep constraints/schema; call pinned skfolio and retain deterministic fallback. |
| Upstream integrations | Health/version/capability adapters; disabled LEAN prototype | WRAP | Process/container isolation, pinned images, timeouts, normalized inputs/outputs. |
| Provenance | Source IDs, checksums, import batches, manifests | EXTEND | Evidence lineage from raw object to feature, hypothesis, experiment, and claim. |
| Reproducibility | Strategy versions, parameters, seeds, source identifiers | KEEP | Add source snapshot, code/data/model/prompt digests and environment lock. |
| Leakage validation | Signal eligibility and later-bar execution rules | EXTEND | Adopt the standard temporal model and dataset-specific point-in-time suites. |
| Frontend | React/Vite typed API, operational and research pages | EXTEND | Add dossier, driver graph, evidence, experiment, divergence, and scenario views. |
| Jobs | Durable import jobs, leases, retries, worker, schedules | EXTEND | Add idempotent DAG steps, distributed rate budgets, dataset watermarks, cancellation. |
| Storage | SQLAlchemy on SQLite/PostgreSQL, normalized tables | EXTEND | PostgreSQL system of record; object store/Parquet for large immutable payloads. |
| Infrastructure | Docker, CI, migrations, health, logs/metrics, supply-chain checks | EXTEND | Add separate worker pools, object storage, queue/lease observability, cost meters. |

### Explicit deprecations

- DEPRECATE SQLite as a scale/performance reference; retain it for local unit tests and demos.
- DEPRECATE fixture-only adapter behavior as evidence of production readiness.
- DEPRECATE in-process scheduling and rate limiting for multi-host deployment.
- DEPRECATE compatibility-only reimplementations once real QuantStats/skfolio adapters pass reconciliation.
- DEPRECATE a fixed global factor list as the primary research abstraction.

## Logical services and boundaries

1. **Source adapters** discover and fetch only. They emit immutable envelopes with source IDs, content hashes, licensing policy, and all known times.
2. **Normalization** resolves identifiers and writes versioned observations; it never erases prior revisions.
3. **Temporal Truth** computes eligibility and rejects ambiguous or impossible time orderings.
4. **Entity/exposure graph** holds typed nodes, versioned edges, provenance, and confidence.
5. **Feature service** produces point-in-time materializations keyed by definition and dataset versions.
6. **Relevance router** selects sources, features, and resolution levels within explicit budgets.
7. **Research control plane** manages hypotheses, experiments, skeptic gates, and memory.
8. **Optional engines** run in isolated processes/containers through stable manifests.
9. **Runtime AI gateway** sends minimal evidence packets through provider-neutral structured-output contracts.

PostgreSQL is the transactional source of truth. Object storage holds raw archives, extracted documents, large arrays, and Parquet partitions. pgvector may index evidence embeddings, but relational identifiers and provenance remain authoritative.

## Scientific and operational invariants

- No observation is visible to a simulation before `simulation_eligible_time`.
- Raw payloads and revisions are immutable; corrections append versions.
- Every feature value resolves to code, parameters, input observations, and data snapshot.
- Every graph edge and AI claim resolves to evidence, method, confidence, and eligibility.
- A model cannot directly promote a hypothesis or place an order.
- Experiment families track multiple-testing budgets and rejected results.
- Production source code is changed only through the normal reviewed development process.
- Missing evidence and uncertainty are represented explicitly; scenarios do not invent precision.

## Scale posture

| Universe | Operating posture | Approximate hot PostgreSQL | Approximate object/Parquet | Routine compute |
|---:|---|---:|---:|---|
| 100 companies | All L0-L2; 20-50 L3; 5-15 L4 | 20-80 GB | 0.2-1 TB | 8-16 vCPU, 32-64 GB RAM; modest batch AI |
| 1,000 companies | All L0-L1; 200-400 L2; 50-100 L3; 10-30 L4 | 100-400 GB | 1-5 TB | 32-64 vCPU batch pool; queue/object store required |
| 5,000 companies | All L0; promotion budgets at every deeper level | 0.4-1.5 TB | 5-25 TB | distributed workers, columnar scans, 64-256 aggregate vCPU |

These are planning ranges, not capacity guarantees. Full Common Crawl, global satellite imagery, or tick/order-book archives are excluded; the router stores references and selected subsets. With mostly free public data, a disciplined beta can target roughly USD 300-1,500/month at 100 companies and USD 1,500-8,000/month at 1,000 companies, dominated by compute, storage/egress, market-data licensing, and bounded AI. A 5,000-company deep-research system is not a single-node beta.

## Decisions before implementation

- Approve the canonical temporal schema and amendment policy.
- Choose object-store deployment and retention tiers.
- Approve upstream license policy, especially LGPL process isolation.
- Select the v0.7 source subset and service-level objectives.
- Define benchmark companies, known drivers, negative controls, and evaluation horizons.
- Define AI data-retention/provider policy before transmitting evidence.

## What not to build

Do not build a new SEC parser, generic backtest engine, optimizer, performance-metric library, graph database, weather model, satellite processing stack, web crawler, vector database, foundation model, or brokerage integration in v0.7. Do not ingest every available dataset, scrape arbitrary pages per company, or turn qualitative model output into trades.
