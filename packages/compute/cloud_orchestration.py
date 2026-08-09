from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.compute.manifests import (
    canonical_checksum,
    validate_result_manifest,
)
from packages.compute.object_store import ArtifactStore
from packages.compute.providers.cloud_run import GoogleCloudRunJobsProvider
from packages.compute.service import spec_from_job, transition_job
from packages.compute.types import ComputeState
from packages.database.models import CloudUsageLedger, ComputeJob


def input_bundle(job: ComputeJob) -> dict[str, Any]:
    return {
        "job_id": str(job.id),
        "workspace_id": str(job.workspace_id),
        "job_type": job.job_type,
        "input_manifest_hash": job.input_manifest_hash,
        "algorithm_version": job.model_version or "phase5-control-plane-v1",
        "items": job.input_manifest.get("items", []),
        "parameters": job.parameters,
        "data_provenance": job.data_provenance,
        "data_version": job.data_version,
    }


def submit_one_cloud_job(
    session: Session,
    provider: GoogleCloudRunJobsProvider,
    store: ArtifactStore,
    *,
    input_bucket: str,
) -> ComputeJob | None:
    job = session.scalar(
        select(ComputeJob)
        .where(
            ComputeJob.state == ComputeState.CLOUD_SUBMITTING.value,
            ComputeJob.selected_provider == provider.name.value,
            ComputeJob.cloud_execution_id.is_(None),
        )
        .order_by(ComputeJob.priority.desc(), ComputeJob.created_at)
        .limit(1)
    )
    if job is None:
        return None
    prefix = f"jobs/{job.id}"
    store.write_json(input_bucket, f"{prefix}/input.json", input_bundle(job))
    try:
        execution = provider.submit(spec_from_job(job))
    except Exception as exc:
        transition_job(
            session,
            job,
            ComputeState.FAILED_RETRYABLE,
            "cloud_submission_failed_without_resubmission",
            {"error_type": type(exc).__name__},
        )
        job.error_classification = "TRANSIENT_PROVIDER"
        job.error_detail = str(exc)[:2000]
        return job
    job.cloud_execution_id = execution.execution_id
    job.attempt_count += 1
    session.add(
        CloudUsageLedger(
            workspace_id=job.workspace_id,
            job_id=job.id,
            provider=provider.name.value,
            estimated_usd=job.estimated_cost_usd,
            observed_usd=None,
            task_count=int(job.parameters.get("task_count") or 1),
            usage_date=datetime.now(UTC).date(),
        )
    )
    transition_job(
        session,
        job,
        ComputeState.CLOUD_QUEUED,
        "cloud_execution_recorded",
        {"execution_id": execution.execution_id},
    )
    return job


def _validate_partition(value: dict[str, Any], job: ComputeJob, index: int) -> tuple[bool, str]:
    expected = value.get("checksum")
    payload = {key: item for key, item in value.items() if key != "checksum"}
    if expected != canonical_checksum(payload):
        return False, "partition_checksum_invalid"
    expected_values = {
        "job_id": str(job.id),
        "workspace_id": str(job.workspace_id),
        "input_manifest_hash": job.input_manifest_hash,
        "algorithm_version": job.model_version or "phase5-control-plane-v1",
        "index": index,
    }
    for key, expected_value in expected_values.items():
        if value.get(key) != expected_value:
            return False, f"partition_{key}_mismatch"
    if not isinstance(value.get("items"), list):
        return False, "partition_items_invalid"
    return True, "validated"


def reconcile_cloud_job(
    session: Session,
    job: ComputeJob,
    provider: GoogleCloudRunJobsProvider,
    store: ArtifactStore,
    *,
    result_bucket: str,
) -> ComputeJob:
    if not job.cloud_execution_id:
        raise ValueError("cloud execution id is required for reconciliation")
    execution = provider.status(job.cloud_execution_id)
    if execution.execution_id != job.cloud_execution_id:
        job.cloud_execution_id = execution.execution_id
    state = ComputeState(execution.state)
    current = ComputeState(job.state)
    if state == ComputeState.CLOUD_QUEUED:
        return job
    if state == ComputeState.CLOUD_RUNNING:
        if current == ComputeState.CLOUD_QUEUED:
            transition_job(session, job, state, "cloud_execution_running")
        return job
    if state == ComputeState.FAILED_RETRYABLE:
        transition_job(session, job, state, "cloud_execution_failed")
        job.error_classification = "TRANSIENT_PROVIDER"
        return job
    if state != ComputeState.RESULT_VALIDATING:
        raise ValueError(f"unsupported provider reconciliation state: {state}")
    if current == ComputeState.CLOUD_QUEUED:
        transition_job(session, job, ComputeState.CLOUD_RUNNING, "cloud_execution_completed")
    transition_job(session, job, ComputeState.RESULT_VALIDATING, "cloud_result_download_started")
    task_count = int(job.parameters.get("task_count") or 1)
    partitions: list[dict[str, Any]] = []
    for index in range(task_count):
        object_name = f"jobs/{job.id}/results/partition-{index:05d}.json"
        value = store.read_json(result_bucket, object_name)
        valid, reason = _validate_partition(value, job, index)
        if not valid:
            transition_job(session, job, ComputeState.FAILED_FINAL, reason)
            job.error_classification = "INVALID_RESULT"
            return job
        partitions.append(
            {
                "index": index,
                "uri": f"gs://{result_bucket}/{object_name}",
                "checksum": value["checksum"],
            }
        )
    manifest: dict[str, Any] = {
        "job_id": str(job.id),
        "workspace_id": str(job.workspace_id),
        "input_manifest_hash": job.input_manifest_hash,
        "algorithm_version": job.model_version or "phase5-control-plane-v1",
        "partitions": partitions,
    }
    manifest["manifest_checksum"] = canonical_checksum(manifest)
    validation = validate_result_manifest(
        manifest,
        job_id=job.id,
        workspace_id=job.workspace_id,
        input_manifest_hash=job.input_manifest_hash,
        algorithm_version=job.model_version or "phase5-control-plane-v1",
        expected_partitions=task_count,
    )
    if not validation.valid:
        transition_job(
            session,
            job,
            ComputeState.FAILED_FINAL,
            "cloud_result_manifest_rejected",
            {"errors": validation.errors},
        )
        job.error_classification = "INVALID_RESULT"
        return job
    job.result_manifest = manifest
    job.error_classification = None
    job.error_detail = None
    transition_job(session, job, ComputeState.SUCCEEDED, "cloud_result_validated")
    return job


def reconcile_one_cloud_job(
    session: Session,
    provider: GoogleCloudRunJobsProvider,
    store: ArtifactStore,
    *,
    result_bucket: str,
) -> ComputeJob | None:
    job = session.scalar(
        select(ComputeJob)
        .where(
            ComputeJob.state.in_(
                [ComputeState.CLOUD_QUEUED.value, ComputeState.CLOUD_RUNNING.value]
            ),
            ComputeJob.selected_provider == provider.name.value,
            ComputeJob.cloud_execution_id.is_not(None),
        )
        .order_by(ComputeJob.updated_at)
        .limit(1)
    )
    if job is None:
        return None
    if job.parameters.get("cancel_requested"):
        provider.cancel(job.cloud_execution_id or "")
        transition_job(session, job, ComputeState.CANCELED, "cloud_cancel_sent")
        job.error_classification = "CANCELED"
        return job
    return reconcile_cloud_job(session, job, provider, store, result_bucket=result_bucket)
