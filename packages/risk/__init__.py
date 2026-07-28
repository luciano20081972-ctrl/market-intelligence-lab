"""Reusable risk constraints for future simulation features."""

from decimal import Decimal


def position_weight(position_value: Decimal, portfolio_value: Decimal) -> Decimal:
    if portfolio_value <= 0:
        raise ValueError("portfolio value must be positive")
    return position_value / portfolio_value
