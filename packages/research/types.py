from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class ResolutionLevel(StrEnum):
    LEVEL_0 = "LEVEL_0"
    LEVEL_1 = "LEVEL_1"
    LEVEL_2 = "LEVEL_2"
    LEVEL_3 = "LEVEL_3"
    LEVEL_4 = "LEVEL_4"


class FeatureQuality(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING_INPUTS = "missing_inputs"
    STALE_INPUTS = "stale_inputs"
    AMBIGUOUS_INPUTS = "ambiguous_inputs"
    LOW_CONFIDENCE_GRAPH = "low_confidence_graph"
    REVISED = "revised"
    TEMPORALLY_UNSAFE = "temporally_unsafe"
    FAILED_COMPUTATION = "failed_computation"


@dataclass(frozen=True)
class FeatureMatrix:
    as_of_time: datetime
    universe_version_id: uuid.UUID
    feature_keys: tuple[str, ...]
    entity_ids: tuple[uuid.UUID, ...]
    values: dict[uuid.UUID, dict[str, Decimal | str | None]]
    feature_value_ids: tuple[uuid.UUID, ...]
    missing: dict[uuid.UUID, tuple[str, ...]]


@dataclass(frozen=True)
class BudgetDecision:
    accepted: tuple[uuid.UUID, ...]
    deferred: tuple[uuid.UUID, ...]
    reason: str
    usage: dict[str, int | float]


@dataclass(frozen=True)
class ScreeningScore:
    entity_id: uuid.UUID
    score: Decimal
    components: dict[str, Decimal]
    reason_codes: tuple[str, ...]
    missing_information: tuple[str, ...]
