# Build-versus-integrate matrix

Decision order: SEARCH → EVALUATE → INTEGRATE/ADAPT → BUILD ONLY IF NECESSARY. Estimates are directional engineer-weeks saved relative to building a credible equivalent, excluding integration and validation.

| Capability | Reuse candidate | Decision | MIL-specific work that remains | Work saved |
|---|---|---|---|---:|
| SEC fetch/parsing/XBRL | SEC bulk APIs + EdgarTools | INTEGRATE | Temporal mapping, bulk watermarks, identity, provenance, normalized schema, fixtures | 12-24 w |
| Market backtesting | Internal oracle + LEAN optional engine | WRAP | Engine manifest, data export, eligibility conformance, result reconciliation | 8-16 w |
| Microstructure simulation | NautilusTrader | EVALUATE/OPTIONAL | LGPL approval, isolated adapter, catalog mapping, conformance | 12-24 w |
| Performance analytics | QuantStats | INTEGRATE | Definition/frequency mapping, reconciliation, canonical result schema | 3-6 w |
| Portfolio optimization | skfolio | INTEGRATE | Constraints, solver governance, out-of-sample validation, fallback | 8-16 w |
| ML research workflow | Qlib | OPTIONAL ENGINE | Point-in-time feature export, experiment/memory bridge, leakage tests | 10-20 w |
| Agentic R&D | RD-Agent | REFERENCE then sandbox | Restricted tasks, research-memory bridge, skeptic gates, model budgets | 6-12 w |
| Financial LLM tasks | FinGPT | REFERENCE ONLY | Own evidence contracts/evals/provider routing | 2-4 w |
| Reinforcement learning | FinRL/FinRL-X | REFERENCE/EVALUATE LATER | Scientific benchmark and realistic environments | 2-6 w |
| Graph persistence/traversal | PostgreSQL recursive CTE | BUILD THIN DOMAIN LAYER | Entity/edge/evidence schema, temporal/RLS, query budgets | Avoids 6-12 w of dual-store ops |
| Graph algorithms | NetworkX | INTEGRATE OFFLINE | Snapshot/export/version bridge | 6-12 w |
| Semantic retrieval | pgvector | OPTIONAL INTEGRATE | Embedding policy, indexes, eval, deterministic confirmation | 4-8 w |
| Geospatial primitives | PostGIS/GDAL/xarray ecosystem | INTEGRATE when needed | Entity mapping, source-specific transforms, temporal lineage | 12-30 w |
| Weather/climate models | NOAA/NASA/ECMWF products | CONSUME DATA | Selection, spatial joins, revisions; never build forecast model | 20-60 w |
| Satellite archive/processing | Landsat/Copernicus cloud/STAC tools | CONSUME/REFERENCE | AOI routing, metadata, derived-product governance | 20-60 w |
| Macro series/vintages | FRED/ALFRED + agency APIs | CONSUME | Release calendar, vintage storage, mapping, tests | 8-16 w |
| Web crawl | Common Crawl indexes/WARC | CONSUME SELECTIVELY | Domain routing, legal policy, extraction, dedup | 20-50 w |
| Durable ingestion state | Existing MIL jobs/leases | EXTEND | DAG steps, distributed budgets, object-store manifests | preserves ~8-12 w |
| Temporal truth | No commodity library owns MIL semantics | BUILD | Canonical envelope, policies, constraints, point-in-time queries/tests | necessary differentiator |
| Relevance router | No mature drop-in | BUILD | Priors, graph/evidence scoring, budgets, exploration, eval | necessary differentiator |
| Hypothesis/memory/divergence | No drop-in with required gates | BUILD THIN CONTROL PLANE | Schemas, state machines, evaluations, skeptic workflow | necessary differentiator |

## Recommended sequence

1. v0.7 builds only Temporal Truth, source manifests, immutable landing/object references, and three high-value adapters (SEC, FRED/ALFRED, one agency feed), using fixtures and bounded live rehearsals.
2. v0.8 builds the relational graph and router with NetworkX offline; no Neo4j.
3. v0.9 adds point-in-time feature materialization and progressive levels.
4. v0.10 adds Qlib and a sandboxed RD-Agent evaluation only after canonical evidence/experiments exist.

## Rejected near-term builds

Generic crawler, graph database, foundation model, weather/satellite model, backtest engine replacement, optimizer, metric library, distributed streaming platform, and real-money execution. Each would consume effort without validating the product's core differentiator: discovering and testing entity-specific drivers under temporal truth.
