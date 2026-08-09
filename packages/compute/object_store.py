from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from packages.compute.manifests import canonical_checksum, canonical_json


class ArtifactStore(Protocol):
    def read_json(self, bucket: str, object_name: str) -> dict[str, object]: ...

    def write_json(self, bucket: str, object_name: str, value: dict[str, object]) -> str: ...


@dataclass(frozen=True)
class GoogleCloudStorageArtifactStore:
    """Private object exchange; credentials come from the runtime identity."""

    def _client(self) -> object:
        try:
            from google.cloud import storage  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is required by the cloud worker") from exc
        return storage.Client()

    def read_json(self, bucket: str, object_name: str) -> dict[str, object]:
        import json

        client = self._client()
        payload = client.bucket(bucket).blob(object_name).download_as_bytes()  # type: ignore[attr-defined]
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise ValueError("job bundle must be a JSON object")
        return value

    def write_json(self, bucket: str, object_name: str, value: dict[str, object]) -> str:
        payload = canonical_json(value)
        client = self._client()
        blob = client.bucket(bucket).blob(object_name)  # type: ignore[attr-defined]
        blob.upload_from_string(payload, content_type="application/json")
        return canonical_checksum(value)
