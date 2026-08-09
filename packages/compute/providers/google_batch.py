from __future__ import annotations

from decimal import Decimal

from packages.compute.providers.base import ProviderExecution, ProviderHealth
from packages.compute.types import ComputeJobSpec, ComputeProviderName


class GoogleBatchProvider:
    """Future Spot/Batch contract; intentionally cannot provision capacity in Phase 5."""

    name = ComputeProviderName.GOOGLE_BATCH

    def health(self) -> ProviderHealth:
        return ProviderHealth(False, "google_batch_future_tier_not_configured")

    def estimate_cost(self, spec: ComputeJobSpec) -> Decimal:
        return spec.estimate.estimated_cost_usd

    def submit(self, spec: ComputeJobSpec) -> ProviderExecution:
        del spec
        raise RuntimeError("google_batch_future_tier_not_configured")

    def status(self, execution_id: str) -> ProviderExecution:
        return ProviderExecution(self.name, execution_id, "CLOUD_DISABLED", "future-tier")

    def cancel(self, execution_id: str) -> ProviderExecution:
        return ProviderExecution(self.name, execution_id, "CANCELED", "future-tier")
