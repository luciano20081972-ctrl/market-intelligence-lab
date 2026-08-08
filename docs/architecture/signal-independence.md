# Signal independence

## Independent Information Score

The score ranks validated candidates by incremental usefulness, not standalone backtest performance.

| Dimension | Example measurement |
|---|---|
| Predictive power | Nested out-of-sample loss reduction, rank IC, or likelihood gain with confidence interval |
| Stability | Sign/effect consistency across folds, entities, definitions, and time |
| Economic plausibility | Predeclared mechanism rubric plus evidence coverage |
| Source reliability/data quality | Completeness, revision rate, lineage, error history |
| Current relevance | Router probability and graph exposure materiality |
| Existing-signal overlap | Partial correlation, conditional mutual information, VIF, residual incremental loss |
| Conventional-information overlap | Increment beyond price, fundamentals, estimates, sector/macro baselines |
| Crowding | Availability/popularity proxy, decay after publication, turnover/concentration |
| Decay | Half-life and delay sensitivity |
| Sector/regime specificity | Out-of-scope failure clarity and regime interaction stability |

## Proposed calculation

First apply blocking gates for leakage, data quality, plausible mechanism, robustness, and skeptic review. Then compute a calibrated 0-100 score:

```text
IIS = 100 * incremental_value
          * stability
          * reliability
          * relevance
          * independence
          * decay_resilience
          * scope_confidence
```

Each component is in `[0,1]`, defined per experiment family, and accompanied by uncertainty. `independence` combines residual contribution and penalties for correlation/source dependence/crowding. Multiplication prevents one excellent dimension from hiding a critical weakness. Weights or transforms must be preregistered and sensitivity-tested.

## Portfolio of signals

Selection maximizes incremental cross-validated objective under turnover, exposure, concentration, and source-dependency constraints. A modest but orthogonal signal may outrank a stronger duplicate. Compare forward selection, regularized models, and Shapley-style conditional contribution only on held-out periods; do not interpret model importance as causality.

Report the score card, uncertainty, baseline set, correlation matrix, regimes, and failure modes. Never publish a bare scalar.
