# Data relevance router

The router converts a company's dynamic driver profile and a budget into an explainable pipeline plan. It prevents universal ingestion and prevents model curiosity from becoming unbounded cost.

## Driver profile

Each `(entity, driver)` record stores:

- prior relevance from sector and business model
- geographic, facility, supplier/customer, commodity, technology, and regulatory exposure evidence
- historical predictive evidence with out-of-sample uncertainty
- source availability/quality/freshness
- user override with author and expiry
- current relevance distribution, not just a label
- last evaluation, next review, supporting and contradicting evidence
- activation/deactivation hysteresis and reason

Example values are calibrated scores in `[0,1]` plus uncertainty: `semiconductor_capacity .94`, `export_controls .92`, `hyperscaler_capex .89`, `Taiwan_geopolitical .81`, `electricity_demand .55`, `agricultural_soil .02`.

## Routing score

```text
route_priority = expected_relevance
               * evidence_quality
               * uncertainty_value
               * freshness_need
               * entity_materiality
               * information_value
               / normalized_cost
```

Hard policy gates run first: license, tenant, geography, credential, retention, temporal suitability, and source health. The score then chooses a source/feature/resolution within daily API, compute, storage, and AI budgets. Every decision writes a reason code and policy version.

## Inputs

1. Sector/business-model priors seed likely drivers but never prove them.
2. Graph exposures raise or lower relevance using evidence and edge confidence.
3. Historical tests contribute only walk-forward, leakage-cleared evidence.
4. Current change detectors raise uncertainty when new facilities, regulations, products, or regions appear.
5. Users can pin, suppress, or challenge a driver; overrides expire and remain audited.

## Relevance changes

Previously irrelevant factors are reconsidered through low-cost sentinels: entity/filing changes, material news/event classifications, graph neighborhood changes, regime alerts, and scheduled exploration. Reserve 5-10% of the processing budget for exploration and negative controls. Activate after a high threshold or repeated evidence; deactivate only below a lower threshold for a minimum dwell time.

## Output contract

The router emits a signed plan containing entity, resolution level, selected datasets/features, skipped candidates with reasons, maximum cost, freshness target, required temporal policy, plan expiry, and policy/model versions. Workers may execute only this plan; they cannot silently add sources.

## Evaluation

- Recall on a curated company-to-driver benchmark, including overlooked drivers.
- Precision/cost: useful validated drivers per compute/API/storage unit.
- Churn and time-to-activation after a known exposure change.
- Sector and geography coverage gaps.
- Counterfactual ablations against route-all and prior-only baselines.
- Calibration of relevance probabilities.

Failure-safe behavior is to preserve the last valid plan, reduce depth when budgets fail, and display stale/partial state—not to route every source.
