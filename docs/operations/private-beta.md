# Private beta operations

The default pipeline is: market-calendar check → due-provider check → ingestion → validation →
raw-object preservation → reconciliation → Temporal Truth eligibility → features → controlled
research maintenance → forecast maturity/scoring → calibration → paper-candidate refresh → manual
paper-plan preview. Each occurrence is persisted and independently observable; later failures do
not erase earlier successful stages.

## Operator checklist

1. Run `python -m scripts.private_beta_readiness` and resolve every FAIL.
2. Confirm Alembic is at the expected revision and PostgreSQL 17 is reachable.
3. Confirm authentication, trusted hosts, and CORS are bounded.
4. Confirm API, market-data worker, operations worker, and scheduler heartbeats are current.
5. Review stale critical data, quarantined jobs, and open alerts.
6. Confirm raw-object storage and free disk thresholds.
7. Create and verify a backup before migration or deployment.
8. Run bounded live smoke checks only with explicit approval and flags.
9. Confirm paper workflows remain MANUAL_PREVIEW or simulated only.
10. Deploy separately; this repository task does not alter the live server.
