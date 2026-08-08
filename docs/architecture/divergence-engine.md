# Divergence engine

The divergence engine identifies unusual disagreement among independently sourced information layers. It does not collapse them into a single sentiment score.

## Representation

Each layer emits an as-of-safe standardized state with direction, magnitude distribution, confidence, freshness, source family, driver/entity scope, and eligibility. Candidate layers include price/volatility, reported fundamentals, guidance, analyst consensus, filings, suppliers/customers, shipping, energy, labor, policy, weather, geospatial activity, scientific/technology trends, and alternative data.

## Detection

1. Align observations by eligible time and forecast horizon.
2. Normalize each layer against its own entity/sector/regime history.
3. Compute pairwise disagreement only where source lineage is sufficiently independent.
4. Compare the current vector with historical joint states using robust distance/change-point methods.
5. Require persistence or corroboration and attach plausible graph transmission paths.

Candidate measures include signed z-score spread, rank disagreement, Jensen-Shannon divergence for distributions, robust Mahalanobis distance, change-point probability, and residuals after removing common factors. Thresholds are learned only on training data and evaluated walk-forward.

## Output

A divergence event contains the disagreeing layers, point-in-time observations, historical rarity, duration, source dependencies, graph paths, alternative explanations, confidence, temporal cutoff, and recommended tests. It is a research trigger—not a buy/sell recommendation.

## Controls

- Do not count several vendors carrying the same origin as independent confirmation.
- Treat stale data, revisions, and missingness as possible explanations.
- Compare against simple baselines and multiple-testing budgets.
- Test whether divergence adds information beyond level/trend features.
- Preserve events that resolved without predictive value.
