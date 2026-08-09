from __future__ import annotations

import json
import os
from typing import Any

from packages.compute.manifests import canonical_checksum
from packages.compute.object_store import ArtifactStore, GoogleCloudStorageArtifactStore
from packages.compute.sharding import deterministic_shards


def execute_partition(
    bundle: dict[str, Any], *, task_index: int, task_count: int
) -> dict[str, object]:
    if task_index < 0 or task_index >= task_count:
        raise ValueError("task index is outside the declared task count")
    items = bundle.get("items")
    if not isinstance(items, list):
        raise ValueError("job bundle items must be a list")
    shard = deterministic_shards(items, task_count)[task_index]
    job_type = str(bundle.get("job_type") or "")
    if job_type != "deterministic_fixture":
        raise ValueError("cloud executor is not registered for this job type")
    output = [
        {"identity": canonical_checksum(item), "input": item, "value": canonical_checksum(item)}
        for item in shard
    ]
    partition = {
        "job_id": str(bundle.get("job_id") or ""),
        "workspace_id": str(bundle.get("workspace_id") or ""),
        "input_manifest_hash": str(bundle.get("input_manifest_hash") or ""),
        "algorithm_version": str(bundle.get("algorithm_version") or ""),
        "index": task_index,
        "task_count": task_count,
        "items": output,
    }
    return {**partition, "checksum": canonical_checksum(partition)}


def run(store: ArtifactStore | None = None) -> int:
    job_id = os.environ["MIL_COMPUTE_JOB_ID"]
    input_bucket = os.environ["MIL_INPUT_BUCKET"]
    result_bucket = os.environ["MIL_RESULT_BUCKET"]
    task_index = int(os.getenv("CLOUD_RUN_TASK_INDEX", "0"))
    task_count = int(os.getenv("CLOUD_RUN_TASK_COUNT", "1"))
    artifact_store = store or GoogleCloudStorageArtifactStore()
    prefix = f"jobs/{job_id}"
    bundle = artifact_store.read_json(input_bucket, f"{prefix}/input.json")
    result = execute_partition(bundle, task_index=task_index, task_count=task_count)
    object_name = f"{prefix}/results/partition-{task_index:05d}.json"
    checksum = artifact_store.write_json(result_bucket, object_name, result)
    print(
        json.dumps(
            {"job_id": job_id, "task_index": task_index, "uri": object_name, "checksum": checksum},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
