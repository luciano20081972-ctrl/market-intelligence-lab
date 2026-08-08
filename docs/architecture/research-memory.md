# Research memory

Research memory is an append-versioned institutional record, not a chat transcript or vector store. It makes evidence, experiments, failures, and later outcomes searchable and reproducible.

## Core records

- `research_question` and entity/sector/regime scope
- hypothesis versions, rationale, mechanism, falsifiers, and evidence
- feature definition and implementation commit
- datasets, licenses, snapshot IDs, exact time ranges and temporal policies
- training/validation/test and walk-forward windows
- metrics, uncertainty, robustness, costs, failures, and logs
- applicable/invalid sectors, regime sensitivity, correlations, independent-information score
- decision, reviewer, skeptic findings, conclusion, supersession
- forecast distribution, realized outcomes, calibration, attribution, and lessons

Artifacts are content-addressed. Large artifacts live in object storage; PostgreSQL stores metadata, hashes, access policy, and lineage. Text and embeddings are derived indexes and can be rebuilt.

## Duplicate prevention

Before proposing work, an agent searches by structured mechanism tuple `(driver, transmission, outcome, horizon, entity scope)`, feature lineage, dataset combination, and semantic similarity. It must cite the nearest prior work and explain novelty. Exact duplicates are linked, not rerun, unless a new data vintage, regime, or method justifies replication.

## Memory tiers

1. **Canonical:** approved structured conclusions and reproducible experiments.
2. **Working:** unreviewed evidence packets, proposals, and partial runs.
3. **Negative:** rejected, failed, null, and contradictory findings.
4. **Outcome:** later realizations, calibration, and attribution.

Canonical conclusions never discard contradictions. A conclusion is time-scoped, sector-scoped, and supersedable. Access uses existing workspace policy; shared public evidence is separate from private notes and hypotheses.

## Retrieval contract

The runtime AI gateway receives a bounded evidence packet: structured prior experiments, exact citations/locators, contradictions, current temporal cutoff, and a token/cost budget. Retrieval logs query, selected/omitted IDs, embedding version, reranker version, and user/workspace. Generated summaries are not evidence unless linked to underlying records.

## Quality metrics

- duplicate experiment rate
- percent of conclusions reproducible from stored manifests
- negative-result retrieval rate
- citation/provenance completeness
- calibration improvement after outcome feedback
- superseded conclusions still used after their validity period (target zero)
