"""Pure strategy signal contracts; no order execution is permitted."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ResearchSignal:
    symbol: str
    observed_at: datetime
    score: float
    explanation: str


class ResearchStrategy(Protocol):
    name: str

    def evaluate(self, symbol: str) -> ResearchSignal: ...
