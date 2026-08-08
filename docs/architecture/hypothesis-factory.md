# Hypothesis factory

The factory turns observations into falsifiable, machine-readable experiments. An LLM may propose or structure a hypothesis; it cannot accept it as an investment signal.

## Lifecycle

```text
observation -> relationship discovery -> hypothesis -> feature specification
-> data-availability check -> implementation -> historical test -> leakage check
-> walk-forward test -> robustness -> independence -> skeptic review
-> accepted / rejected / inconclusive -> research memory -> later outcome
```

State transitions are explicit and audited. Rejected and inconclusive work is retained to reduce publication bias and duplicate experimentation.

## Proposed record

```yaml
hypothesis_id: hyp_uuid
entity_scope: [company_or_sector_ids]
claim: "Regional electricity-price increases compress Company X margins."
mechanism:
  cause: regional_power_price
  transmission: electricity_intensive_facilities
  outcome: operating_margin
  expected_direction: negative
evidence_requirements:
  - facility_locations
  - power_intensity_or_proxy
  - regional_power_prices
  - point_in_time_margin_releases
feature:
  name: weighted_regional_power_price_change_90d
  definition_version: 1
forecast_horizon: P1Q
falsification:
  minimum_effect: declared_before_test
  invalidating_observations: [hedged_power_costs, immaterial_energy_share]
temporal_policy_id: policy_uuid
experiment_family_id: family_uuid
status: proposed
```

The persisted form additionally references creator type, prompt/model or rule version, source evidence, data snapshot, code commit, environment lock, train/validation/test windows, costs, preregistered metrics, and decision rationale.

## Gates

1. **Specificity:** named cause, transmission mechanism, outcome, direction, horizon, and falsifier.
2. **Availability:** required data can be acquired legally with resolvable identity and time.
3. **Temporal:** every input has an approved eligibility policy.
4. **Implementation:** deterministic feature code, tests, lineage, missingness behavior.
5. **Statistics:** holdout/walk-forward, effect and uncertainty, realistic costs, baseline comparison.
6. **Robustness:** alternative windows, definitions, subperiods, sectors, regimes, perturbations.
7. **Multiplicity:** experiment-family budget, false-discovery control or adjusted inference.
8. **Independence:** incremental contribution beyond existing/conventional signals.
9. **Skeptic:** blocking red-team report resolved or explicitly waived by an authorized human.

## Skeptic/red-team agent

The skeptic has read access to evidence and experiments and can only challenge, request tests, or block promotion. It searches for look-ahead leakage, survivorship/selection bias, multiple testing, stale inputs, wrong entity links, alternative mechanisms, regime dependence, unstable correlations, execution assumptions, costs, revisions, and contradictory evidence. Its findings are structured with severity, evidence, reproducible check, and resolution. It cannot rewrite results or source code.

No factor reaches `paper-active` unless temporal, robustness, independence, and skeptic gates pass and a human approves the transition. Brokerage/real-money execution remains out of scope.

## Self-evaluation

At the forecast horizon, store the predicted distribution, actual outcome, calibration error, factor and agent contribution, assumptions that failed, useful/misleading evidence, and regime. Aggregate outcomes update agent reliability, route priority, factor confidence, dataset information value, and hypothesis priors. They do not autonomously modify production code or relax gates.
