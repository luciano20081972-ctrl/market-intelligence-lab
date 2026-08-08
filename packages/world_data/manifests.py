from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

SAFE_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")


class SourceManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    dataset_id: str
    source_version: str | None = None
    schema_version: str = "1"
    parser_version: str
    retrieval_time: datetime
    source_updated_time: datetime | None = None
    temporal_coverage_start: datetime | None = None
    temporal_coverage_end: datetime | None = None
    raw_object_reference: str
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    checksum_algorithm: str = "sha256"
    byte_count: int = Field(ge=0)
    record_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    license_identifier: str
    job_id: str | None = None
    parent_manifest_id: str | None = None

    @field_validator("source_id", "dataset_id")
    @classmethod
    def safe_identifier(cls, value: str) -> str:
        if not SAFE_IDENTIFIER.fullmatch(value):
            raise ValueError("identifier must be lowercase and path-safe")
        return value

    @field_validator(
        "retrieval_time",
        "source_updated_time",
        "temporal_coverage_start",
        "temporal_coverage_end",
    )
    @classmethod
    def aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("manifest timestamps must be timezone-aware")
        return value


DataManifest = SourceManifest


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
