from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from packages.compute.providers.base import ProviderExecution, ProviderHealth
from packages.compute.types import ComputeJobSpec, ComputeProviderName


class CloudRunTransport(Protocol):
    def post(self, path: str, payload: dict[str, Any], *, request_id: str) -> dict[str, Any]: ...

    def get(self, path: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CloudRunConfiguration:
    project_id: str
    region: str
    job_name: str
    image: str
    input_bucket: str
    result_bucket: str
    service_account: str
    max_parallel_tasks: int = 1

    def __post_init__(self) -> None:
        if "@sha256:" not in self.image:
            raise ValueError("Cloud Run worker image must use an immutable sha256 digest")
        if self.max_parallel_tasks < 1:
            raise ValueError("max_parallel_tasks must be positive")


class GoogleCloudRunJobsProvider:
    name = ComputeProviderName.GOOGLE_CLOUD_RUN_JOBS

    def __init__(
        self,
        configuration: CloudRunConfiguration | None,
        transport: CloudRunTransport | None = None,
    ) -> None:
        self.configuration = configuration
        self.transport = transport

    def health(self) -> ProviderHealth:
        if self.configuration is None:
            return ProviderHealth(False, "cloud_run_not_configured")
        if self.transport is None:
            return ProviderHealth(False, "cloud_run_authentication_unavailable")
        return ProviderHealth(True, "cloud_run_configured")

    def estimate_cost(self, spec: ComputeJobSpec) -> Decimal:
        return spec.estimate.estimated_cost_usd

    def execution_payload(self, spec: ComputeJobSpec) -> dict[str, Any]:
        config = self.configuration
        if config is None:
            raise RuntimeError("Cloud Run is not configured")
        task_count = min(spec.estimate.task_count, config.max_parallel_tasks)
        return {
            "overrides": {
                "taskCount": task_count,
                "timeout": f"{spec.estimate.runtime_seconds}s",
                "containerOverrides": [
                    {
                        "name": "worker",
                        "env": [
                            {"name": "MIL_COMPUTE_JOB_ID", "value": str(spec.job_id)},
                            {"name": "MIL_COMPUTE_WORKSPACE_ID", "value": str(spec.workspace_id)},
                            {"name": "MIL_INPUT_MANIFEST_HASH", "value": spec.input_manifest_hash},
                            {"name": "MIL_INPUT_BUCKET", "value": config.input_bucket},
                            {"name": "MIL_RESULT_BUCKET", "value": config.result_bucket},
                            {"name": "MIL_WORKER_IMAGE", "value": config.image},
                        ],
                    }
                ],
            },
        }

    def submit(self, spec: ComputeJobSpec) -> ProviderExecution:
        health = self.health()
        if not health.available or self.configuration is None or self.transport is None:
            raise RuntimeError(health.detail)
        path = (
            f"/v2/projects/{self.configuration.project_id}/locations/"
            f"{self.configuration.region}/jobs/{self.configuration.job_name}:run"
        )
        response = self.transport.post(
            path, self.execution_payload(spec), request_id=spec.submission_key
        )
        execution_id = str(response.get("name") or "")
        if not execution_id:
            raise RuntimeError("Cloud Run response did not include an execution name")
        return ProviderExecution(self.name, execution_id, "CLOUD_QUEUED", spec.submission_key)

    def status(self, execution_id: str) -> ProviderExecution:
        if self.transport is None:
            raise RuntimeError("cloud_run_authentication_unavailable")
        response = self.transport.get(f"/v2/{execution_id.lstrip('/')}")
        active_id = execution_id
        if "/operations/" in execution_id:
            if not response.get("done"):
                return ProviderExecution(self.name, execution_id, "CLOUD_QUEUED", "reconciled")
            if response.get("error"):
                return ProviderExecution(self.name, execution_id, "FAILED_RETRYABLE", "reconciled")
            operation_result = response.get("response")
            if not isinstance(operation_result, dict) or not operation_result.get("name"):
                return ProviderExecution(self.name, execution_id, "FAILED_RETRYABLE", "reconciled")
            active_id = str(operation_result["name"])
            response = operation_result
        failed = int(response.get("failedCount") or 0)
        completed = int(response.get("succeededCount") or 0)
        tasks = int(response.get("taskCount") or 0)
        if failed:
            state = "FAILED_RETRYABLE"
        elif response.get("completionTime") or (tasks and completed >= tasks):
            state = "RESULT_VALIDATING"
        elif int(response.get("runningCount") or 0):
            state = "CLOUD_RUNNING"
        else:
            state = "CLOUD_QUEUED"
        return ProviderExecution(self.name, active_id, state, "reconciled")

    def cancel(self, execution_id: str) -> ProviderExecution:
        if self.transport is None:
            raise RuntimeError("cloud_run_authentication_unavailable")
        self.transport.post(
            f"/v2/{execution_id.lstrip('/')}:cancel",
            {},
            request_id=f"cancel:{execution_id}",
        )
        return ProviderExecution(self.name, execution_id, "CANCELED", "reconciled")
