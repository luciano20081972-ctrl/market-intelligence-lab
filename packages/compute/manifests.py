from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def canonical_checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class ResultValidation:
    valid: bool
    errors: tuple[str, ...]


def validate_result_manifest(
    manifest: dict[str, Any],
    *,
    job_id: UUID,
    workspace_id: UUID,
    input_manifest_hash: str,
    algorithm_version: str,
    expected_partitions: int,
) -> ResultValidation:
    errors: list[str] = []
    if manifest.get("job_id") != str(job_id):
        errors.append("job_id_mismatch")
    if manifest.get("workspace_id") != str(workspace_id):
        errors.append("workspace_id_mismatch")
    if manifest.get("input_manifest_hash") != input_manifest_hash:
        errors.append("input_manifest_hash_mismatch")
    if manifest.get("algorithm_version") != algorithm_version:
        errors.append("algorithm_version_mismatch")
    partitions = manifest.get("partitions")
    if not isinstance(partitions, list):
        errors.append("partitions_missing")
        partitions = []
    indexes: list[int] = []
    for item in partitions:
        index = item.get("index") if isinstance(item, dict) else None
        if isinstance(index, int):
            indexes.append(index)
    if len(indexes) != len(partitions) or sorted(indexes) != list(range(expected_partitions)):
        errors.append("partitions_incomplete_or_duplicate")
    for item in partitions:
        if not isinstance(item, dict) or not item.get("checksum") or not item.get("uri"):
            errors.append("partition_manifest_invalid")
            break
    expected_checksum = manifest.get("manifest_checksum")
    payload = {key: value for key, value in manifest.items() if key != "manifest_checksum"}
    if expected_checksum != canonical_checksum(payload):
        errors.append("manifest_checksum_invalid")
    return ResultValidation(not errors, tuple(errors))
