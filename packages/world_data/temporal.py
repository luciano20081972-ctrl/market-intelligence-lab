from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from packages.core.time import as_utc


class QualityFlag(StrEnum):
    MISSING = "missing"
    REVISED = "revised"
    ESTIMATED = "estimated"
    PRELIMINARY = "preliminary"
    OUTLIER = "outlier"
    DUPLICATE = "duplicate"
    MALFORMED = "malformed"
    STALE = "stale"
    UNIT_MISMATCH = "unit_mismatch"
    TEMPORAL_AMBIGUITY = "temporal_ambiguity"


class TemporalTruth(BaseModel):
    """Seven-clock record used to prevent future information from entering simulations."""

    model_config = ConfigDict(frozen=True)

    event_time: datetime
    observation_time: datetime
    publication_time: datetime
    retrieval_time: datetime
    effective_time: datetime
    revision_time: datetime
    simulation_eligible_time: datetime
    precision: str = "second"
    source_time_zone: str = "UTC"
    quality_flags: tuple[QualityFlag, ...] = ()

    @field_validator(
        "event_time", "observation_time", "publication_time", "retrieval_time",
        "effective_time", "revision_time", "simulation_eligible_time",
    )
    @classmethod
    def require_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Temporal truth timestamps must be timezone-aware")
        return as_utc(value)

    @model_validator(mode="after")
    def enforce_eligibility_floor(self) -> TemporalTruth:
        floor = max(self.publication_time, self.retrieval_time, self.revision_time)
        if self.simulation_eligible_time < floor:
            raise ValueError(
                "simulation_eligible_time cannot precede publication, retrieval, or revision"
            )
        return self

    def visible_as_of(self, as_of: datetime) -> bool:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return self.simulation_eligible_time <= as_utc(as_of)


SOURCE_TEMPORAL_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "sec": ("accepted_at", "filing_date", "retrieval_time"),
    "fred": ("observation_date", "retrieval_time"),
    "alfred": ("observation_date", "realtime_start", "realtime_end", "retrieval_time"),
    "eia": ("period", "retrieval_time"),
}
