# Progressive-resolution research

The universe moves through increasingly expensive levels. Counts are policy parameters constrained by daily budgets, not fixed product promises.

| Level | Typical universe | Work | Promotion examples |
|---|---:|---|---|
| L0 | 1,000-5,000 | Price/liquidity, canonical financial availability, identity/eligibility | Investability, freshness, liquidity, anomaly or user priority |
| L1 | 500-5,000 | Structured SEC + macro + standard factors | Material change, uncertainty, baseline opportunity, data completeness |
| L2 | 100-1,000 | Sector/business/geography routed sources and graph exposures | Driver materiality, novel divergence, validated source availability |
| L3 | 20-200 | Deep external datasets, documents, geospatial/event joins | High expected information value and decision relevance |
| L4 | 5-30 | AI dossier, hypotheses, skeptic review, scenarios | Human-approved candidate/research queue |

Promotion score combines relevance, expected information gain, uncertainty, freshness, data quality, materiality, portfolio/user priority, and cost. Demotion follows stale evidence, low realized value, failed hypotheses, reduced uncertainty, missing data, or budget pressure. Hysteresis and minimum dwell times prevent thrashing.

## Budgeting and fairness

Set daily quotas for API calls, bytes, CPU/GPU time, AI tokens, and per-source concurrency. Reserve exploration and negative-control budgets. Enforce sector/geography coverage floors so a popular sector does not consume the universe. Persist every promotion/demotion reason and counterfactual score.

## Reproducibility

A resolution run records policy version, universe snapshot, features and eligibility cutoff, budget, rankings, random seed for exploration, selected/skipped entities, and downstream artifacts. Replay must produce the same plan from the same snapshot.

## Scale recommendation

- 100 companies: L0-L2 for all, bounded L3 for 20-50, L4 for 5-15.
- 1,000: L0-L1 for all, L2 for 200-400, L3 for 50-100, L4 for 10-30.
- 5,000: L0 for all; L1 and deeper strictly promoted. Do not promise deep dossiers for all.
