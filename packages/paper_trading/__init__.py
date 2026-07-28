"""Simulation-only portfolio types; this package cannot submit brokerage orders."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SimulatedPosition:
    symbol: str
    quantity: Decimal
    average_price: Decimal
