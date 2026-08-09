from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class FreshnessClassification(StrEnum):
    REAL_TIME = "REAL_TIME"
    DELAYED = "DELAYED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FreshnessResult:
    source: str
    market_timestamp: datetime | None
    received_at: datetime
    processed_at: datetime
    age_seconds: int | None
    classification: FreshnessClassification


def classify_freshness(
    source: str,
    market_timestamp: datetime | None,
    received_at: datetime,
    processed_at: datetime | None = None,
    *,
    realtime_seconds: int = 60,
    delayed_seconds: int = 1200,
) -> FreshnessResult:
    processed = processed_at or datetime.now(UTC)
    if market_timestamp is None:
        return FreshnessResult(
            source,
            None,
            received_at,
            processed,
            None,
            FreshnessClassification.UNKNOWN,
        )
    if market_timestamp.tzinfo is None or received_at.tzinfo is None or processed.tzinfo is None:
        raise ValueError("freshness timestamps must include timezones")
    age = max(0, int((processed - market_timestamp).total_seconds()))
    if age <= realtime_seconds:
        classification = FreshnessClassification.REAL_TIME
    elif age <= delayed_seconds:
        classification = FreshnessClassification.DELAYED
    else:
        classification = FreshnessClassification.STALE
    return FreshnessResult(source, market_timestamp, received_at, processed, age, classification)
