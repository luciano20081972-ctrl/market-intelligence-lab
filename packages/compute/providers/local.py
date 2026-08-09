from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from packages.compute.providers.base import ProviderExecution, ProviderHealth
from packages.compute.types import ComputeJobSpec, ComputeProviderName


class LocalComputeProvider:
    name = ComputeProviderName.LOCAL

    def __init__(self, executor: Callable[[ComputeJobSpec], dict[str, Any]] | None = None) -> None:
        self.executor = executor
        self._executions: dict[str, ProviderExecution] = {}

    def health(self) -> ProviderHealth:
        return ProviderHealth(True, "local_control_plane_available")

    def estimate_cost(self, spec: ComputeJobSpec) -> Decimal:
        del spec
        return Decimal("0")

    def submit(self, spec: ComputeJobSpec) -> ProviderExecution:
        existing = self._executions.get(spec.submission_key)
        if existing:
            return existing
        execution = ProviderExecution(
            self.name, str(spec.job_id), "LOCAL_RUNNING", spec.submission_key
        )
        self._executions[spec.submission_key] = execution
        if self.executor is not None:
            self.executor(spec)
            execution = ProviderExecution(
                self.name, str(spec.job_id), "SUCCEEDED", spec.submission_key
            )
            self._executions[spec.submission_key] = execution
        return execution

    def status(self, execution_id: str) -> ProviderExecution:
        return next(
            (item for item in self._executions.values() if item.execution_id == execution_id),
            ProviderExecution(self.name, execution_id, "FAILED_FINAL", "unknown"),
        )

    def cancel(self, execution_id: str) -> ProviderExecution:
        current = self.status(execution_id)
        cancelled = ProviderExecution(self.name, execution_id, "CANCELED", current.submission_key)
        self._executions[current.submission_key] = cancelled
        return cancelled
