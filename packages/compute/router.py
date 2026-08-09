from __future__ import annotations

from dataclasses import dataclass

from packages.compute.budget import BudgetLimits, BudgetUsage, evaluate_budget
from packages.compute.resource_guard import LocalResourceGuard, ResourceSnapshot
from packages.compute.types import ComputeJobSpec, ComputeProviderName, ComputeState, JobClass


@dataclass(frozen=True)
class ProviderAvailability:
    cloud_run: bool = False
    google_batch: bool = False


@dataclass(frozen=True)
class RouteDecision:
    state: ComputeState
    provider: ComputeProviderName | None
    reason: str


class ComputeRouter:
    def __init__(self, resource_guard: LocalResourceGuard) -> None:
        self.resource_guard = resource_guard

    def route(
        self,
        spec: ComputeJobSpec,
        snapshot: ResourceSnapshot,
        limits: BudgetLimits,
        usage: BudgetUsage,
        availability: ProviderAvailability,
    ) -> RouteDecision:
        local = self.resource_guard.evaluate(spec.job_class, spec.estimate, snapshot)
        if spec.job_class == JobClass.INTERACTIVE_LIGHT:
            if local.allowed:
                return RouteDecision(ComputeState.QUEUED, ComputeProviderName.LOCAL, local.reason)
            return RouteDecision(ComputeState.WAITING_FOR_CAPACITY, None, local.reason)

        if spec.job_class == JobClass.STANDARD and local.allowed:
            return RouteDecision(ComputeState.QUEUED, ComputeProviderName.LOCAL, local.reason)

        budget = evaluate_budget(
            spec.estimate.estimated_cost_usd,
            spec.estimate.runtime_seconds,
            spec.estimate.task_count,
            limits,
            usage,
            per_job_ceiling=spec.max_cost_usd,
        )
        if not budget.allowed:
            state = (
                ComputeState.CLOUD_DISABLED
                if budget.reason == "cloud_compute_disabled"
                else ComputeState.BLOCKED_BY_BUDGET
            )
            return RouteDecision(state, None, budget.reason)

        if spec.job_class == JobClass.VERY_HEAVY:
            if availability.google_batch:
                return RouteDecision(
                    ComputeState.CLOUD_SUBMITTING,
                    ComputeProviderName.GOOGLE_BATCH,
                    "very_heavy_google_batch",
                )
            return RouteDecision(
                ComputeState.WAITING_FOR_CAPACITY, None, "google_batch_not_configured"
            )

        if availability.cloud_run:
            return RouteDecision(
                ComputeState.CLOUD_SUBMITTING,
                ComputeProviderName.GOOGLE_CLOUD_RUN_JOBS,
                "cloud_run_selected",
            )
        return RouteDecision(ComputeState.CLOUD_DISABLED, None, "cloud_run_unavailable")
