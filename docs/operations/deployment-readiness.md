# Deployment readiness

Run `python -m scripts.private_beta_readiness` or add `--json` for automation. Categories are
APPLICATION, DATABASE, AUTH, DATA, SCHEDULER, WORKERS, STORAGE, BACKUP, SECURITY, OBSERVABILITY,
and PAPER_SAFETY, each with PASS/WARN/FAIL. Critical failures fail readiness; there is no opaque AI
score. Deployment and production migration remain separate approvals.
