# Economic entity and driver graph

## v0.8 implementation status

Implemented in v0.8: workspace-scoped canonical entities and identifiers, aliases and manual resolution decisions, evidence-backed typed relationships, versioned confidence decomposition, deterministic SEC structured extraction, series linking through intermediate concepts, bounded as-of traversal, path explanations, quality findings, company profiles, and durable recomputation requests. The schema uses `economic_entities` and `economic_relationships`; names below describe the architectural concepts rather than literal table names.

The measured beta design remains PostgreSQL-first. Neo4j, Apache AGE, NetworkX production processing, pgvector identity matching, materialized exposure summaries, statistical correlation edges, and scenario propagation are not implemented. The original five-million-edge acceptance benchmark remains a later scale gate; v0.8 validates the requested 10K/50K shape and optionally 100K/500K where resources permit.

## Beta choice

Use PostgreSQL tables, recursive CTEs, ordinary indexes, PostGIS where spatial joins are approved, and optional pgvector for semantic retrieval. Use NetworkX on bounded exported subgraphs for research algorithms. Do not require Neo4j for beta.

This choice keeps tenancy, transactions, migrations, provenance, temporal versions, and operational skills in one system. Revisit a dedicated graph store only after measured queries cannot meet an agreed SLO despite appropriate indexes/materialized paths, or when graph algorithms over tens of millions of active edges become a dominant workload.

## Canonical model

`entity`

- `id`, `workspace_scope`, `entity_type`, `canonical_name`, `status`
- stable external identifiers in a separate versioned `entity_identifier` table
- implemented types include Company, Security, Subsidiary, BusinessSegment, Product, Facility, Supplier, Customer, Competitor, Commodity, Technology, Country, Region, Port, TransportationNode, EnergyMarket, GovernmentAgency, Regulation, EconomicSeries, ResearchTopic, Industry, and Event

`relationship`

- `id`, `from_entity_id`, `to_entity_id`, `relationship_type`
- implemented types include OWNS, OPERATES, HAS_SEGMENT, PRODUCES, USES, SUPPLIES, BUYS_FROM, SELLS_TO, COMPETES_WITH, LOCATED_IN, EXPOSED_TO, DEPENDS_ON, REGULATED_BY, CONSUMES, SHIPS_THROUGH, USES_TECHNOLOGY, AFFECTED_BY, HAS_SECURITY, and TRACKED_BY_SERIES
- `confidence`, `confidence_method`, `magnitude`, `units`, `polarity`, `directness`
- `valid_from`, `valid_to`, `discovered_at`, `last_verified_at`, `simulation_eligible_time`
- `origin` (`manual`, `rule`, `extraction`, `statistical`), `method_version`, `status`

Evidence is many-to-many through `relationship_evidence`: source observation/document, exact locator, quoted-span hash, extraction method, support/contradict direction, weight, and provenance chain. A relationship without evidence cannot become active. `CORRELATED_WITH` is descriptive and must not be presented as causal.

## Identity and versioning

- Canonical IDs are internal UUIDs, never tickers or vendor IDs.
- Identifiers have namespace, valid interval, confidence, and source.
- Merges are reversible alias events; they do not rewrite historical evidence.
- Edges are append-versioned. Conflicting edges coexist with evidence and confidence.
- Workspace assertions may overlay shared public entities without modifying canonical public records.
- Recursive traversal always constrains relationship types, depth, validity clock, eligibility clock, and tenant scope.

## Query/index posture

- B-tree indexes on both edge directions, `(relationship_type, from_entity_id)`, validity/eligibility, and identifiers.
- Partial indexes for active/high-confidence edges; composite indexes must match measured filters.
- Recursive CTE depth defaults to 3 and has row/time budgets.
- Materialized one/two-hop exposure summaries serve common dossiers and scenario propagation.
- JSONB stores source-specific extras only, not keys used for referential integrity.
- pgvector finds candidate evidence/entities; deterministic identifiers and confidence gates confirm links.

## Technology comparison

| Option | Strength | Cost/risk | Recommendation |
|---|---|---|---|
| PostgreSQL adjacency tables + recursive CTE | Transactions, RLS, temporal/provenance joins, current operations | Complex graph algorithms need exports/materializations | PRIMARY |
| pgvector | Semantic evidence/entity candidate retrieval in PostgreSQL | Approximate similarity is not identity or causality | OPTIONAL EXTENSION |
| NetworkX (BSD-3-Clause) | Rich algorithms, easy bounded experimentation | In-memory; not concurrent system of record | RESEARCH TOOL |
| Apache AGE (Apache-2.0) | Cypher-like graph extension inside PostgreSQL | Extra extension lifecycle and operational uncertainty | EVALUATE AFTER BENCHMARK |
| Neo4j Community (GPL-3.0) | Mature traversal/query ergonomics | Separate store, synchronization, licensing/operations | REJECT FOR BETA; reconsider at measured need |

## Acceptance benchmark before a graph database

Generate a representative 5 million-edge dataset and measure: 1-3 hop exposure traversal, temporal-as-of traversal, evidence expansion, scenario propagation, and top driver aggregation. The beta target is p95 under 500 ms for interactive bounded queries and under 30 s for asynchronous portfolio propagation. A dedicated graph database is considered only if PostgreSQL misses these targets after indexes, bounded traversal, and materialized summaries.

Sources: [PostgreSQL recursive queries](https://www.postgresql.org/docs/current/queries-with.html), [pgvector](https://github.com/pgvector/pgvector), [NetworkX](https://github.com/networkx/networkx), [Apache AGE](https://github.com/apache/age), [Neo4j license](https://github.com/neo4j/neo4j/blob/dev/LICENSE.txt).
