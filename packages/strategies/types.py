from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class SignalDecision:
    target_weight: float | None
    direction: str
    strength: float
    explanation: str
    factors: dict[str, float]


SignalFunction = Callable[[Sequence[float], int, BaseModel], SignalDecision]


@dataclass(frozen=True)
class StrategyDefinition:
    key: str
    name: str
    description: str
    calculation_notes: str
    parameters_model: type[BaseModel]
    generate: SignalFunction
