from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from packages.market_data.types import CorporateActionRecord, HistoricalBarRecord

SUPPORTED_ACTION_TYPES = {"split", "reverse_split", "dividend", "symbol_change"}


def validate_corporate_action(action: CorporateActionRecord) -> None:
    if action.action_type not in SUPPORTED_ACTION_TYPES:
        raise ValueError(f"unsupported corporate action '{action.action_type}'")
    if action.action_type in {"split", "reverse_split"} and (
        action.ratio is None or action.ratio <= 0
    ):
        raise ValueError("split and reverse-split actions require a positive ratio")
    if action.action_type == "dividend" and (
        action.amount is None or action.amount < 0 or not action.currency
    ):
        raise ValueError("dividend actions require a nonnegative amount and currency")
    if action.action_type == "symbol_change" and (not action.old_symbol or not action.new_symbol):
        raise ValueError("symbol changes require old_symbol and new_symbol")


def adjusted_close_for(
    bar: HistoricalBarRecord, actions: Iterable[CorporateActionRecord]
) -> Decimal:
    """Return a deterministic backward-adjusted close while preserving raw close."""
    value = bar.close
    for action in sorted(actions, key=lambda item: item.effective_time):
        validate_corporate_action(action)
        if bar.event_time >= action.effective_time:
            continue
        if action.action_type in {"split", "reverse_split"} and action.ratio:
            value /= action.ratio
        elif action.action_type == "dividend" and action.amount:
            value = max(Decimal("0.000001"), value - action.amount)
    return value


def adjustment_status(actions: Iterable[CorporateActionRecord]) -> str:
    action_types = sorted({action.action_type for action in actions})
    return "+".join(action_types) if action_types else "unadjusted"
