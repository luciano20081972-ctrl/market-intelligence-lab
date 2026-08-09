from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BudgetLimits:
    cloud_enabled: bool = False
    max_job_usd: Decimal = Decimal("0.25")
    max_daily_usd: Decimal = Decimal("0.50")
    max_monthly_usd: Decimal = Decimal("5.00")
    max_parallel_tasks: int = 1
    max_runtime_seconds: int = 900
    spend_cap_blocked: bool = False

    def __post_init__(self) -> None:
        if min(self.max_job_usd, self.max_daily_usd, self.max_monthly_usd) < 0:
            raise ValueError("budget limits cannot be negative")
        if self.max_parallel_tasks < 1 or self.max_parallel_tasks > 10_000:
            raise ValueError("max_parallel_tasks must be between 1 and 10000")
        if self.max_runtime_seconds < 1:
            raise ValueError("max_runtime_seconds must be positive")


@dataclass(frozen=True)
class BudgetUsage:
    daily_usd: Decimal = Decimal("0")
    monthly_usd: Decimal = Decimal("0")
    active_tasks: int = 0


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str


def evaluate_budget(
    estimated_usd: Decimal,
    runtime_seconds: int,
    task_count: int,
    limits: BudgetLimits,
    usage: BudgetUsage,
    *,
    per_job_ceiling: Decimal | None = None,
) -> BudgetDecision:
    if not limits.cloud_enabled:
        return BudgetDecision(False, "cloud_compute_disabled")
    if limits.spend_cap_blocked:
        return BudgetDecision(False, "cloud_run_spend_cap_blocked")
    ceiling = min(limits.max_job_usd, per_job_ceiling or limits.max_job_usd)
    if estimated_usd > ceiling:
        return BudgetDecision(False, "per_job_cost_limit")
    if usage.daily_usd + estimated_usd > limits.max_daily_usd:
        return BudgetDecision(False, "daily_cost_limit")
    if usage.monthly_usd + estimated_usd > limits.max_monthly_usd:
        return BudgetDecision(False, "monthly_cost_limit")
    if runtime_seconds > limits.max_runtime_seconds:
        return BudgetDecision(False, "runtime_limit")
    if task_count + usage.active_tasks > limits.max_parallel_tasks:
        return BudgetDecision(False, "parallel_task_limit")
    return BudgetDecision(True, "within_budget")
