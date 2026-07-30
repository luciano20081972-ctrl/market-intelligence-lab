from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from packages.core.time import utc_now
from packages.database.models import BacktestReproducibilityManifest, BacktestRun


def dependency_lock_checksum(root: Path | None = None) -> str:
    project_root = root or Path.cwd()
    digest = hashlib.sha256()
    found = False
    for name in ("pyproject.toml", "apps/web/pnpm-lock.yaml"):
        path = project_root / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes())
            found = True
    return digest.hexdigest() if found else "unavailable"


def git_commit_sha(root: Path | None = None) -> str:
    configured = os.getenv("MIL_GIT_SHA")
    if configured:
        return configured[:64]
    try:
        executable = shutil.which("git")
        if executable is None:
            return "unavailable"
        result = subprocess.run(
            [executable, "rev-parse", "HEAD"],
            cwd=root or Path.cwd(),
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return result.stdout.strip() or "unavailable"


def build_manifest(run: BacktestRun) -> dict[str, object]:
    strategy = run.strategy_version.strategy
    manifest: dict[str, object] = {
        "application_version": run.application_version,
        "git_commit_sha": git_commit_sha(),
        "strategy_id": str(strategy.id),
        "strategy_version_id": str(run.strategy_version_id),
        "strategy_version": run.strategy_version.version,
        "strategy_parameters": run.strategy_configuration,
        "risk_configuration": run.risk_configuration,
        "execution_assumptions": run.execution_assumptions,
        "dependency_lock_checksum": dependency_lock_checksum(),
        "provider_ids": run.provider_identifiers,
        "provider_versions": "unavailable",
        "import_job_ids": run.import_job_identifiers,
        "dataset_checksums": run.execution_assumptions.get("dataset_checksums", "unavailable"),
        "adjustment_state": run.adjustment_statuses,
        "exchange_calendar_library": "exchange-calendars",
        "exchange_calendar_version": importlib.metadata.version("exchange-calendars"),
        "calendar_code": run.calendar_code,
        "calendar_range": {"start": run.start_time.isoformat(), "end": run.end_time.isoformat()},
        "corporate_action_dataset_version": "unavailable",
        "data_source_classification": run.data_classification,
        "random_seed": 0,
        "start_date": run.start_time.isoformat(),
        "end_date": run.end_time.isoformat(),
        "benchmark": run.benchmark_symbol,
        "generated_at": utc_now().isoformat(),
    }
    return manifest


def create_manifest(session: Session, run: BacktestRun) -> BacktestReproducibilityManifest:
    manifest = build_manifest(run)
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    value = BacktestReproducibilityManifest(
        backtest_run_id=run.id,
        manifest=manifest,
        manifest_checksum=hashlib.sha256(canonical.encode()).hexdigest(),
    )
    session.add(value)
    return value
