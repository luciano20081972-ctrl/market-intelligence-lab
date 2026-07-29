from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from packages.market_data.types import HistoricalBarRecord

SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.\-]{0,15}$")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str
    record_identifier: str | None = None


@dataclass
class ValidationReport:
    records_checked: int = 0
    valid_records: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def as_dict(self) -> dict[str, object]:
        return {
            "records_checked": self.records_checked,
            "valid_records": self.valid_records,
            "is_valid": self.is_valid,
            "issues": [asdict(issue) for issue in self.issues],
            "counts_by_code": {
                code: sum(1 for issue in self.issues if issue.code == code)
                for code in sorted({issue.code for issue in self.issues})
            },
        }


def validate_symbol(symbol: str) -> bool:
    return bool(SYMBOL_PATTERN.fullmatch(symbol.strip().upper()))


def validate_historical_bars(
    records: Iterable[HistoricalBarRecord],
    *,
    valid_session_dates: set[str] | None = None,
    stale_after_days: int = 7,
    now: datetime | None = None,
) -> ValidationReport:
    report = ValidationReport()
    seen: set[tuple[str, str, datetime]] = set()
    current_time = now or datetime.now(UTC)
    for record in records:
        report.records_checked += 1
        identifier = f"{record.symbol}:{record.interval}:{record.event_time.isoformat()}"
        before = len(report.issues)
        if not validate_symbol(record.symbol):
            report.issues.append(
                ValidationIssue(
                    "invalid_symbol", f"Invalid symbol '{record.symbol}'.", "error", identifier
                )
            )
        timestamps = (
            record.event_time,
            record.publication_time,
            record.effective_time,
            record.retrieval_time,
        )
        if any(value is None or value.tzinfo is None for value in timestamps):
            report.issues.append(
                ValidationIssue(
                    "missing_or_naive_timestamp",
                    (
                        "All event, publication, effective, and retrieval times "
                        "must be timezone-aware."
                    ),
                    "error",
                    identifier,
                )
            )
        if (
            record.high < max(record.open, record.close)
            or record.low > min(record.open, record.close)
            or record.high < record.low
        ):
            report.issues.append(
                ValidationIssue(
                    "impossible_ohlc",
                    "OHLC values are internally inconsistent.",
                    "error",
                    identifier,
                )
            )
        if min(
            record.open, record.high, record.low, record.close, record.adjusted_close
        ) <= Decimal("0"):
            report.issues.append(
                ValidationIssue(
                    "nonpositive_price", "Prices must be positive.", "error", identifier
                )
            )
        if record.volume < 0:
            report.issues.append(
                ValidationIssue(
                    "negative_volume", "Volume cannot be negative.", "error", identifier
                )
            )
        key = (record.symbol.upper(), record.interval, record.event_time)
        if key in seen:
            report.issues.append(
                ValidationIssue(
                    "duplicate_bar",
                    "Duplicate symbol/interval/event-time bar.",
                    "error",
                    identifier,
                )
            )
        seen.add(key)
        if (
            valid_session_dates is not None
            and record.event_time.date().isoformat() not in valid_session_dates
        ):
            report.issues.append(
                ValidationIssue(
                    "missing_session",
                    "Bar falls on a closed exchange session.",
                    "error",
                    identifier,
                )
            )
        if current_time - record.retrieval_time > timedelta(days=stale_after_days):
            report.issues.append(
                ValidationIssue(
                    "stale_import",
                    "Retrieval timestamp exceeds the freshness threshold.",
                    "warning",
                    identifier,
                )
            )
        if len(report.issues) == before:
            report.valid_records += 1
    return report
