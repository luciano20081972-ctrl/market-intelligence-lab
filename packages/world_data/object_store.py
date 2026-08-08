from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RawObjectMetadata:
    key: str
    checksum: str
    byte_count: int
    media_type: str


class RawObjectStore(Protocol):
    def put(self, key: str, payload: bytes, media_type: str) -> RawObjectMetadata: ...
    def metadata(self, key: str) -> RawObjectMetadata: ...
    def exists(self, key: str) -> bool: ...
    def verify_checksum(self, key: str) -> bool: ...


def immutable_object_key(
    provider: str, dataset: str, retrieved_at: datetime, checksum_or_id: str
) -> str:
    safe = (provider, dataset, checksum_or_id)
    if any(not part or "/" in part or "\\" in part or ".." in part for part in safe):
        raise ValueError("raw-object key components must be path-safe")
    return (
        f"{provider}/{dataset}/{retrieved_at:%Y/%m/%d}/{checksum_or_id}"
    )


class LocalRawObjectStore:
    """Local immutable adapter with semantics shared by S3/R2/Supabase adapters."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if self.root not in candidate.parents:
            raise ValueError("raw-object key escapes configured root")
        return candidate

    def put(self, key: str, payload: bytes, media_type: str) -> RawObjectMetadata:
        path = self._path(key)
        checksum = hashlib.sha256(payload).hexdigest()
        if path.exists():
            if path.read_bytes() != payload:
                raise FileExistsError("immutable raw object already exists with different content")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        path.with_suffix(path.suffix + ".meta").write_text(
            f"{checksum}\n{len(payload)}\n{media_type}\n", encoding="utf-8"
        )
        return RawObjectMetadata(key, checksum, len(payload), media_type)

    def metadata(self, key: str) -> RawObjectMetadata:
        path = self._path(key)
        checksum, byte_count, media_type = path.with_suffix(path.suffix + ".meta").read_text(
            encoding="utf-8"
        ).splitlines()
        return RawObjectMetadata(key, checksum, int(byte_count), media_type)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def verify_checksum(self, key: str) -> bool:
        path = self._path(key)
        return hashlib.sha256(path.read_bytes()).hexdigest() == self.metadata(key).checksum
