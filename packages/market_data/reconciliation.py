from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import (
    Asset,
    ImportError,
    ImportJob,
    PriceBar,
    Provider,
    ReconciliationIssue,
    ReconciliationRun,
    TradingSession,
)


def preview_reconciliation(
    session: Session,
    *,
    provider_id: UUID | None = None,
    symbols: list[str] | None = None,
    stale_after_days: int = 7,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    query = select(PriceBar, Asset).join(Asset, PriceBar.asset_id == Asset.id)
    if provider_id:
        query = query.where(PriceBar.provider_id == provider_id)
    if symbols:
        query = query.where(Asset.symbol.in_([item.upper() for item in symbols]))
    rows = session.execute(query.order_by(Asset.symbol, PriceBar.event_time)).all()
    valid_sessions = set(session.scalars(select(TradingSession.session_date)).all())
    key_counts = Counter(
        (bar.provider_id, bar.asset_id, bar.interval, bar.event_time) for bar, _asset in rows
    )
    canonical_counts = Counter((bar.asset_id, bar.interval, bar.event_time) for bar, _asset in rows)
    issues: list[dict[str, Any]] = []
    latest: dict[str, datetime] = {}
    previous: dict[str, datetime] = {}
    for bar, asset in rows:
        identifier = f"{asset.symbol}:{bar.interval}:{bar.event_time.isoformat()}"
        if key_counts[(bar.provider_id, bar.asset_id, bar.interval, bar.event_time)] > 1:
            issues.append(
                {"type": "duplicate_provider_record", "severity": "error", "record": identifier}
            )
        if canonical_counts[(bar.asset_id, bar.interval, bar.event_time)] > 1:
            issues.append(
                {"type": "duplicate_canonical_record", "severity": "error", "record": identifier}
            )
        if bar.event_time.date().isoformat() not in valid_sessions:
            issues.append({"type": "closed_session_bar", "severity": "error", "record": identifier})
        if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
            issues.append({"type": "invalid_ohlc", "severity": "error", "record": identifier})
        if bar.volume < 0:
            issues.append({"type": "negative_volume", "severity": "error", "record": identifier})
        elif bar.volume == 0:
            issues.append(
                {"type": "zero_volume_anomaly", "severity": "warning", "record": identifier}
            )
        if not bar.original_symbol or bar.original_symbol.upper() != asset.symbol.upper():
            issues.append({"type": "symbol_mismatch", "severity": "error", "record": identifier})
        if bar.adjustment_status == "unadjusted" and bar.adjusted_close != bar.close:
            issues.append(
                {"type": "adjustment_inconsistency", "severity": "error", "record": identifier}
            )
        prior = previous.get(asset.symbol)
        if prior and bar.event_time - prior > timedelta(days=7):
            issues.append(
                {"type": "unexpected_date_gap", "severity": "warning", "record": identifier}
            )
        previous[asset.symbol] = bar.event_time
        latest[asset.symbol] = max(latest.get(asset.symbol, bar.event_time), bar.event_time)
    for symbol, latest_time in latest.items():
        if current - latest_time > timedelta(days=stale_after_days):
            issues.append({"type": "stale_latest_bar", "severity": "warning", "record": symbol})
    by_symbol: dict[str, set[str]] = {}
    for bar, asset in rows:
        by_symbol.setdefault(asset.symbol, set()).add(bar.event_time.date().isoformat())
    for symbol, observed in by_symbol.items():
        first, last = min(observed), max(observed)
        expected = {value for value in valid_sessions if first <= value <= last}
        for missing in sorted(expected - observed):
            issues.append(
                {
                    "type": "missing_expected_session",
                    "severity": "warning",
                    "record": f"{symbol}:{missing}",
                }
            )
    conflict_query = (
        select(ImportError)
        .join(ImportJob, ImportError.job_id == ImportJob.id)
        .where(ImportError.error_code == "conflicting_reimport")
    )
    if provider_id:
        conflict_query = conflict_query.where(ImportJob.provider_id == provider_id)
    for conflict in session.scalars(conflict_query).all():
        issues.append(
            {
                "type": "checksum_change",
                "severity": "error",
                "record": conflict.record_identifier or str(conflict.id),
                "existing_checksum": conflict.payload_summary.get("existing_checksum"),
                "incoming_checksum": conflict.payload_summary.get("incoming_checksum"),
            }
        )
    return {
        "dry_run": True,
        "records_checked": len(rows),
        "issue_count": len(issues),
        "conflict_count": sum(
            item["type"]
            in {"duplicate_provider_record", "duplicate_canonical_record", "checksum_change"}
            for item in issues
        ),
        "issues": issues,
    }


def run_reconciliation(
    session: Session,
    *,
    provider_id: UUID | None = None,
    symbols: list[str] | None = None,
    dry_run: bool = True,
) -> ReconciliationRun:
    if provider_id is not None and session.get(Provider, provider_id) is None:
        raise ValueError("provider was not found")
    report = preview_reconciliation(session, provider_id=provider_id, symbols=symbols)
    run = ReconciliationRun(
        provider_id=provider_id,
        status="succeeded",
        dry_run=dry_run,
        configuration={"symbols": symbols or []},
        records_checked=int(report["records_checked"]),
        issue_count=int(report["issue_count"]),
        conflict_count=int(report["conflict_count"]),
        completed_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()
    for issue in report["issues"]:
        session.add(
            ReconciliationIssue(
                run_id=run.id,
                provider_id=provider_id,
                issue_type=str(issue["type"]),
                severity=str(issue["severity"]),
                record_identifier=str(issue["record"]),
                outcome="preserved",
                resolution_decision="dry_run" if dry_run else "manual_review",
                existing_checksum=issue.get("existing_checksum"),
                incoming_checksum=issue.get("incoming_checksum"),
                details={"mutated": False},
            )
        )
    session.flush()
    return run
