# Information value and cost

Information efficiency controls ingestion and expensive analysis. It is not an investment-return claim.

## Score

```text
Information Efficiency = validated incremental contribution * reliability * coverage * timeliness
                         / (API + compute + storage + egress + AI + maintenance + compliance cost)
```

Contribution is measured on preregistered downstream tasks using walk-forward/holdout comparisons against the current source set. Report confidence intervals and sector/regime scope. A source can be valuable for identity or risk even when it has no direct predictive score, so `decision_value_type` distinguishes predictive, coverage, safety, identity, and operational value.

## Cost ledger

Per source/pipeline record calls, bytes, rows accepted/rejected, CPU/GPU seconds, storage class and retention, egress, AI tokens, failures/retries, on-call incidents, schema changes, license/compliance effort, and engineering hours. Attribute shared costs by documented allocation rules.

## Decisions

- **Increase:** high marginal value, unmet coverage, stable operation.
- **Hold:** useful but saturated or uncertain.
- **Reduce resolution/frequency:** redundant or low marginal value.
- **Suspend:** license/quality/security failure or sustained negative value.
- **Explore:** uncertain source with a bounded experiment budget.

Do not remove safety, provenance, or temporal controls because their short-horizon predictive contribution appears low. Use a minimum observation window and human review before deactivating a source. The router consumes this score together with relevance and uncertainty; it does not optimize the ratio alone.

## Beta dashboard

Display value by source/sector/task, monthly spend, marginal contribution, freshness/coverage, failures, revision burden, and recommended action. Store the score definition, evaluation dataset, baseline, code version, and decision so it is reproducible.
