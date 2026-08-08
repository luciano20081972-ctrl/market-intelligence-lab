# Scenario and counterfactual engine

Scenarios are reusable, versioned shocks propagated through evidence-backed graph paths. They support thesis testing and exposure analysis, not precise price targets.

## Scenario record

- named shocks with distributions/ranges, units, effective interval, and source/rationale
- dependencies and mutually exclusive assumptions
- graph traversal policy: allowed edge types, directions, maximum depth, confidence floor
- transmission functions with evidence level (`estimated`, `bounded`, `qualitative`)
- affected entities, intermediate drivers, lag distributions, uncertainty, and contradictions
- baseline data snapshot and simulation clock

Example shocks: export controls tighten; AI capex +20%; Treasury yields +50 bp; Taiwan shipping unchanged; HBM supply constrained. The engine traverses only valid and simulation-eligible edges, deduplicates converging paths, and prevents cyclical double counting.

## Propagation levels

1. **Exposure map:** graph reachability and qualitative direction.
2. **Bounded sensitivity:** user/research-supplied elasticities with ranges.
3. **Estimated model:** validated historical response with uncertainty and regime limits.

Results preserve the weakest support level along each path. Unsupported paths remain qualitative. Aggregation uses distributions/ranges and sensitivity tables, not false point precision.

## Counterfactuals

For “what would have to change for this thesis to fail?”, identify the minimum assumption/edge/shock changes that reverse or neutralize the outcome within constraints. Return several feasible sets, their evidence, and whether the change is observable. Counterfactuals challenge a thesis; they do not assert causal identification.

## Validation

Replay known historical scenarios using only then-eligible graph/data versions, compare predicted direction/range with outcomes, measure coverage/calibration, and record failed transmission assumptions. The skeptic checks circular paths, stale edges, hidden common causes, elasticity extrapolation, and correlated shocks.
