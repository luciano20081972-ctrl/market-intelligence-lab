# Open-source capability audit

Audit date: 2026-08-07. Releases and activity were checked against GitHub repository metadata; licenses were checked from each repository's LICENSE file. Pin exact versions/digests and repeat license/security review before integration. “Commercial use” below is engineering guidance, not legal advice.

## Required projects

### QuantConnect LEAN — OPTIONAL_ENGINE

- **Repository/release/activity:** [QuantConnect/Lean](https://github.com/QuantConnect/Lean), `v2.4.0.1`; active C# repository, default branch `master` (pushed 2026-08-07 in audit).
- **License/implications:** Apache-2.0; generally permissive with notice/patent obligations. Network use adds no copyleft trigger. QuantConnect cloud/CLI/data services have separate terms and paid-tier requirements.
- **Platform/boundary:** mature event-driven backtest/live engine; C# core with Python algorithms, strongest on Linux/Docker and cross-platform .NET. Local Docker/CLI and filesystem/job/results boundaries; Python interop is not a simple in-process library.
- **Performance/maturity:** high-throughput compiled engine with broad asset/data/execution modeling and long production history.
- **Overlap/reuse:** backtesting, execution models, result statistics, live architecture. Reuse as an isolated conformance/advanced simulation engine.
- **Do not copy:** engine internals, brokerage/live connectivity, or vendor/cloud assumptions into MIL. Do not make it the canonical data/provenance model.
- **Recommendation/work saved:** container/process adapter with normalized manifest and results; 8-16 engineer-weeks versus building comparable breadth. [Official LEAN docs](https://www.lean.io/docs/v2/lean-engine/class-reference/), [local Docker backtest](https://www.lean.io/docs/v2/lean-cli/backtesting/deployment).

### Microsoft Qlib — OPTIONAL_ENGINE

- **Repository/release/activity:** [microsoft/qlib](https://github.com/microsoft/qlib), `v0.9.7`; active Python repository (pushed 2026-07-23).
- **License/implications:** MIT; permissive. No network copyleft; model/data dependencies retain their own terms.
- **Platform/boundary:** Python research platform for dataset expressions, models, workflow tracking, portfolio/backtest analysis. Linux is the safest production target; Windows may work but native/ML dependencies and examples require conformance testing. Docker/container or subprocess workflow using versioned YAML/config and exported artifacts.
- **Performance/maturity:** mature vectorized/ML research workflow; dataset preparation and model training can be memory/CPU/GPU intensive.
- **Overlap/reuse:** feature/model workflow, experiment records, forecasting benchmarks, walk-forward research patterns.
- **Do not copy:** Qlib's storage schema/data collectors as MIL truth, example datasets as licensed production feeds, or its backtest results without MIL temporal reconciliation.
- **Recommendation/work saved:** integrate in v0.10 after Temporal Truth/feature export exists; 10-20 engineer-weeks. [Qlib documentation](https://qlib.readthedocs.io/en/stable/).

### Microsoft RD-Agent — ARCHITECTURE_REFERENCE initially, OPTIONAL_ENGINE after evaluation

- **Repository/release/activity:** [microsoft/RD-Agent](https://github.com/microsoft/RD-Agent), `v0.8.0`; active Python repository (pushed 2026-08-04).
- **License/implications:** MIT; permissive. Runtime LLM providers, containers, datasets, and generated code have separate terms. Network use itself adds no copyleft.
- **Platform/boundary:** multi-agent R&D loops, including quantitative factor/model co-optimization. Linux/container is preferred; Windows support is dependency- and scenario-sensitive. Boundary should be a sandboxed experiment task and artifact bundle, never direct database/code mutation.
- **Performance/maturity:** innovative and active but operationally complex, LLM/compute intensive, and less predictable than deterministic pipelines.
- **Overlap/reuse:** proposal/implementation/evaluation orchestration patterns, experiment loops.
- **Do not copy:** unrestricted autonomous coding, provider-specific prompt stacks, or promotion logic. Do not grant production credentials or source mutation.
- **Recommendation/work saved:** study and run offline benchmark after research-memory gates; 6-12 engineer-weeks if its loop is adopted rather than rebuilt. [Project overview](https://github.com/microsoft/RD-Agent).

### EdgarTools — DIRECT_DEPENDENCY behind adapter

- **Repository/release/activity:** [dgunning/edgartools](https://github.com/dgunning/edgartools), `v5.45.1`; very active Python repository (pushed 2026-08-08 UTC during audit). MIL currently pins 5.43.1, so upgrade requires compatibility review.
- **License/implications:** MIT; permissive. SEC fair-access and user-agent policies still apply; no network copyleft.
- **Platform/boundary:** Python API for entities, filings, structured filing objects, XBRL facts/statements, Forms 3/4/5, 13F, and more. Windows/Linux; normal Python package, optional cache/network behavior wrapped by MIL.
- **Performance/maturity:** mature high-level parser; large-corpus work still needs bulk acquisition, caching, throttling, and normalized persistence.
- **Overlap/reuse:** SEC fetch/parsing/XBRL semantics. Preserve MIL identifiers, Temporal Truth, provenance, and raw hashes.
- **Do not copy:** parser internals or expose library objects as API/database contracts.
- **Recommendation/work saved:** use for filing/document parsing; pair with native SEC bulk ingestion; 12-24 engineer-weeks. [XBRL docs](https://edgartools.readthedocs.io/en/latest/xbrl/).

### skfolio — DIRECT_DEPENDENCY behind adapter

- **Repository/release/activity:** [skfolio/skfolio](https://github.com/skfolio/skfolio), `v0.20.1`; active Python repository (pushed 2026-07-31).
- **License/implications:** BSD-3-Clause; permissive attribution/no-endorsement. No network copyleft.
- **Platform/boundary:** scikit-learn-style portfolio optimization, model selection, uncertainty sets, risk measures, constraints, validation/stress testing. Windows/Linux Python; normal in-process adapter, with solver-specific terms checked separately. Docker friendly.
- **Performance/maturity:** stable API but pre-1.0 versioning; convex and cross-validation workloads vary by solver/universe.
- **Overlap/reuse:** replace compatibility-only optimizer while retaining MIL constraint and result schemas.
- **Do not copy:** optimization algorithms or treat in-sample optimum as investment validation.
- **Recommendation/work saved:** direct pinned adapter plus deterministic fallback/reconciliation; 8-16 engineer-weeks. [Official docs](https://skfolio.org/).

### QuantStats — DIRECT_DEPENDENCY behind adapter

- **Repository/release/activity:** [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats), `v0.0.81`; active Python repository (pushed 2026-07-20).
- **License/implications:** Apache-2.0; permissive with notice/patent obligations. No network copyleft.
- **Platform/boundary:** Python stats, plots, HTML reports/tear sheets and Monte Carlo helpers; Windows/Linux, in-process or report subprocess, Docker friendly.
- **Performance/maturity:** widely used and adequate for daily-return analytics; pandas-bound and not a simulation engine.
- **Overlap/reuse:** canonical performance metrics/reports, reconciled against MIL definitions.
- **Do not copy:** metric implementations, generated visual design, or silently accept frequency/annualization defaults.
- **Recommendation/work saved:** real adapter replacing compatibility-only calculations where definitions match; 3-6 engineer-weeks. [Project README](https://github.com/ranaroussi/quantstats).

### NautilusTrader — OPTIONAL_ENGINE

- **Repository/release/activity:** [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader), `v1.231.0`; very active Rust/Python repository, default `develop` (pushed 2026-08-08 UTC during audit).
- **License/implications:** LGPL-3.0. Dynamic linking and distribution obligations require explicit legal/policy review; modifications to LGPL components must remain compliant. Network service alone is not AGPL, but isolation does not erase distribution obligations.
- **Platform/boundary:** Rust-native event-driven backtest/live infrastructure with Python control/strategies, Parquet catalog, multi-venue adapters. Linux/container preferred; published wheels/platform support must be pinned and tested on Windows. One node per process favors process isolation.
- **Performance/maturity:** high-performance deterministic simulation/order-book focus; v1/v2/PyO3 paths are evolving.
- **Overlap/reuse:** advanced market microstructure/backtest/event architecture, not world-intelligence ingestion.
- **Do not copy:** LGPL internals, live-trading paths, domain objects, or unstable v2 APIs into proprietary core.
- **Recommendation/work saved:** optional research engine only after license/conformance approval; 12-24 engineer-weeks. [Official docs](https://nautilustrader.io/docs/latest/), [Rust paths](https://nautilustrader.io/docs/latest/concepts/rust/).

### FinGPT — REFERENCE_ONLY

- **Repository/release/activity:** [AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT), `v1.0.0`; active primarily notebook repository (pushed 2026-08-02).
- **License/implications:** repository MIT; base models, weights, datasets, APIs, and model outputs have independent licenses/terms. Network providers are separately governed.
- **Platform/boundary:** data-centric financial LLM pipelines, fine-tuning, sentiment/RAG/forecasting examples; Python/Jupyter, typically Linux/GPU, containerizable but not a stable MIL service API.
- **Performance/maturity:** influential research ecosystem; reproducibility and production hardening vary by notebook/model.
- **Overlap/reuse:** task/evaluation ideas and data-centric architecture.
- **Do not copy:** weights/data without per-artifact review, legacy provider defaults, notebook code as production, or sentiment as a signal.
- **Recommendation/work saved:** reference and benchmark selected tasks; no core dependency. 2-4 engineer-weeks of design insight. [Project README](https://github.com/AI4Finance-Foundation/FinGPT).

### FinRL — REFERENCE_ONLY; evaluate FinRL-X separately

- **Repository/release/activity:** [AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL), `v0.3.8`; active in 2026 but its README identifies classic FinRL as educational/research and directs production work to FinRL-X.
- **License/implications:** MIT code with a trademark notice; datasets/providers/environments have separate terms. No network copyleft.
- **Platform/boundary:** Python/Jupyter market environments, DRL agents, applications; Windows instructions exist, but Linux/GPU/container is preferable. Experiment subprocess/container only.
- **Performance/maturity:** established research benchmark; DRL is compute-heavy, unstable, and scientifically high risk for limited financial samples.
- **Overlap/reuse:** environment/benchmark patterns and negative-control experiments.
- **Do not copy:** educational pipelines, Yahoo-derived assumptions, trained agents, or live-trading claims into production.
- **Recommendation/work saved:** reference only; separately audit [FinRL-X/FinRL-Trading](https://github.com/AI4Finance-Foundation/FinRL-Trading) before any future engine decision. 2-6 engineer-weeks of benchmark design. [FinRL architecture](https://finrl.readthedocs.io/en/latest/developer_guide/file_architecture.html).

## Additional overlapping projects

| Project | Release/license/activity | Classification | Use / caution / estimated savings |
|---|---|---|---|
| [pgvector](https://github.com/pgvector/pgvector) | Active; PostgreSQL-style license in LICENSE; pin an extension release/commit | OPTIONAL_DEPENDENCY | Evidence/entity candidate similarity while PostgreSQL remains truth; never use nearest-neighbor output as identity. Saves 4-8 weeks. |
| [NetworkX](https://github.com/networkx/networkx) | `3.6.1`, BSD-3-Clause, active | DIRECT_DEPENDENCY for offline research | Graph algorithms on bounded snapshots; not persistence or online multi-tenant serving. Saves 6-12 weeks. |
| [Apache AGE](https://github.com/apache/age) | Active Apache-2.0 graph extension | OPTIONAL_DEPENDENCY, benchmark later | Cypher-like queries without separate store; adds extension operations/version coupling. Saves uncertain until benchmark. |
| [Neo4j Community](https://github.com/neo4j/neo4j) | Active, GPL-3.0 Community; commercial offerings separate | REJECTED for beta | Strong graph ergonomics but additional store/sync/license boundary lacks measured need. |
| [FinRL-X](https://github.com/AI4Finance-Foundation/FinRL-Trading) | Active 2026 successor; license/artifacts require a separate audit | ARCHITECTURE_REFERENCE | More relevant than classic FinRL for future modular experiments; not yet part of core recommendation. |

## Integration rules

1. Search/evaluate first; adopt only when a maintained project supplies roughly 70% of a bounded capability.
2. Pin package/image/repository digest and record LICENSE, notices, SBOM, vulnerabilities, model/data terms, and transitive licenses.
3. GPL/AGPL/LGPL or commercial internals are never copied into proprietary core without explicit policy approval.
4. External objects do not cross MIL API/database boundaries; normalized manifests do.
5. Offline fixtures and conformance tests are mandatory; “installed” and “live-reachable” are separate health states.
6. Every engine runs with time, memory, network, filesystem, credential, and output limits.
