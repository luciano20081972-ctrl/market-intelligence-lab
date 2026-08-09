from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from packages.compute.types import ComputeJobSpec, ComputeProviderName


@dataclass(frozen=True)
class ProviderHealth:
    available: bool
    detail: str


@dataclass(frozen=True)
class ProviderExecution:
    provider: ComputeProviderName
    execution_id: str
    state: str
    submission_key: str


class ComputeProvider(Protocol):
    name: ComputeProviderName

    def health(self) -> ProviderHealth: ...

    def estimate_cost(self, spec: ComputeJobSpec) -> Decimal: ...

    def submit(self, spec: ComputeJobSpec) -> ProviderExecution: ...

    def status(self, execution_id: str) -> ProviderExecution: ...

    def cancel(self, execution_id: str) -> ProviderExecution: ...
