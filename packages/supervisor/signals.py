from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from typing import Any

from packages.supervisor.freshness import FreshnessClassification, FreshnessResult


class Decision(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    WATCH = "WATCH"
    AVOID = "AVOID"


@dataclass(frozen=True)
class SignalCandidate:
    symbol: str
    decision: Decision
    confidence: Decimal
    horizon: str
    market_regime: str
    trend: dict[str, Any]
    momentum: dict[str, Any]
    volatility: dict[str, Any]
    liquidity: dict[str, Any]
    factor_evidence: list[dict[str, Any]]
    strategy_consensus: dict[str, Any]
    contradicting_signals: list[dict[str, Any]]
    entry_zone: dict[str, Any]
    invalidation_rule: str
    risk_reference: dict[str, Any]
    strategy_version: str
    reproducibility_manifest: dict[str, Any]
    freshness: FreshnessResult

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("confidence must be between zero and one")
        if not self.invalidation_rule.strip():
            raise ValueError("an invalidation rule is required")


def evaluate_signal(candidate: SignalCandidate) -> SignalCandidate:
    if candidate.freshness.classification in {
        FreshnessClassification.STALE,
        FreshnessClassification.UNKNOWN,
    }:
        return replace(
            candidate,
            decision=Decision.WATCH,
            confidence=min(candidate.confidence, Decimal("0.25")),
            contradicting_signals=[
                *candidate.contradicting_signals,
                {"kind": "freshness_guard", "classification": candidate.freshness.classification},
            ],
        )
    return candidate
