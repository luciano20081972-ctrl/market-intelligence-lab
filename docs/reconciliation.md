# Reconciliation

Reconciliation is non-destructive. Preview mode evaluates canonical bars without writing a report. Recorded mode persists a run and issue rows but still never rewrites prices. Checks include missing expected XNYS sessions, bars on closed sessions, provider and canonical duplicates, invalid OHLC relationships, negative and zero volume, stale latest bars, unexpected gaps, symbol mismatches, adjustment inconsistencies, and checksum/conflicting-reimport evidence.

Conflicting imports preserve the existing canonical record, record both checksums in an import error, and later surface the conflict as a reconciliation issue. Outcomes are `preserved`; resolution is `dry_run` or `manual_review`. Automated overwrite is intentionally unsupported.

```powershell
python scripts/operations.py reconcile
python scripts/operations.py reconcile --record
```

## Cross-provider quorum

`POST /api/v1/reconciliation/provider-comparison` aligns overlapping sessions from two explicit providers and records relative OHLC/volume differences, missing/duplicate sessions, adjustment/checksum/freshness differences, tolerances, and unavailable corporate-action comparison. Outcomes are agreed, within tolerance, conflict, or unresolved; accepted-primary, accepted-secondary, and excluded require an explicit resolution reason and audit event. Comparison never overwrites a bar or selects the more favorable value.
