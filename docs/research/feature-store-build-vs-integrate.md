# Feature-store build vs integrate

## Decision

Use a minimal PostgreSQL-native feature store for the beta. PostgreSQL stores definitions, recent immutable values, lineage metadata, point lookups, matrices, policies, snapshots, and candidate state. Add Parquet/Arrow for dense immutable history after measured history exceeds roughly 10 million rows or 10 GB; revisit PostgreSQL partitioning around 100 million rows. Do not add online serving, Spark, Kafka, or a distributed control plane before measurements require them.

| Option | Strength | Mismatch / burden | Decision |
|---|---|---|---|
| [Feast](https://docs.feast.dev/getting-started/concepts/point-in-time-joins) (Apache-2.0) | Standard point-in-time training joins and offline/online serving | Registry plus serving infrastructure; PostgreSQL offline store is contrib; MIL still needs seven clocks, manifests, graph/evidence lineage, revisions, and workspace semantics | Revisit for future online inference; do not adopt in v0.9 |
| [Qlib](https://qlib.readthedocs.io/en/stable/) (MIT) | Mature financial data/research abstractions; Windows declared; Parquet support | Research/model platform rather than MIL provenance/availability system | Integrate later for hypothesis validation, not canonical feature truth |
| PostgreSQL-native | Transactions, authorization, Temporal Truth, joins, constraints, Windows/CI simplicity | Dense matrices become row-heavy | Adopt for beta |
| [Arrow/Parquet](https://arrow.apache.org/docs/python/parquet.html) + PostgreSQL metadata (Apache-2.0) | Column pruning, predicate pushdown, partitioned immutable matrices, local/cloud filesystems | Object lifecycle, atomic publication, metadata consistency, and CI complexity | Documented scale-out path |

Popularity was not a selection criterion. Temporal correctness and reproducibility dominate online-serving features for this release.
