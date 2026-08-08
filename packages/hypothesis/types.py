from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol


class HypothesisStatus(StrEnum):
    DRAFT = "DRAFT"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    READY_FOR_IMPLEMENTATION = "READY_FOR_IMPLEMENTATION"
    IMPLEMENTED = "IMPLEMENTED"
    TESTING = "TESTING"
    REJECTED = "REJECTED"
    PROMISING = "PROMISING"
    VALIDATED = "VALIDATED"
    RETIRED = "RETIRED"


class PromotionStage(StrEnum):
    DRAFT = "DRAFT"
    EVIDENCE_CHECKED = "EVIDENCE_CHECKED"
    IMPLEMENTED = "IMPLEMENTED"
    LEAKAGE_CHECKED = "LEAKAGE_CHECKED"
    BACKTESTED = "BACKTESTED"
    WALK_FORWARD_PASSED = "WALK_FORWARD_PASSED"
    ROBUSTNESS_PASSED = "ROBUSTNESS_PASSED"
    OOS_PASSED = "OOS_PASSED"
    PAPER_ELIGIBLE = "PAPER_ELIGIBLE"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class TimePartition:
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    test_start: datetime
    test_end: datetime
    purge_observations: int = 0
    embargo_observations: int = 0


@dataclass(frozen=True)
class FactorMetrics:
    pearson_ic: float
    spearman_ic: float
    hit_rate: float
    coverage: float
    missingness: float
    quantile_monotonicity: float
    top_minus_bottom: float
    turnover: float
    autocorrelation: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReasoningRequest:
    subject: dict[str, Any]
    graph_paths: tuple[dict[str, Any], ...]
    evidence: tuple[dict[str, Any], ...]
    datasets: tuple[str, ...]
    maximum_hypotheses: int = 10


@dataclass(frozen=True)
class ReasoningCandidate:
    title: str
    rationale: str
    mechanism: dict[str, Any]
    required_evidence: tuple[dict[str, Any], ...]
    feature_specification: dict[str, Any]
    falsification_criteria: tuple[str, ...]


class ResearchReasoningProvider(Protocol):
    name: str

    def available(self) -> bool: ...

    def generate_hypotheses(self, request: ReasoningRequest) -> list[ReasoningCandidate]: ...

    def critique_mechanism(self, mechanism: dict[str, Any]) -> list[str]: ...

    def suggest_required_evidence(self, mechanism: dict[str, Any]) -> list[dict[str, Any]]: ...

    def suggest_feature_specification(self, mechanism: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class EngineStatus:
    engine: str
    version: str | None
    available: bool
    enabled: bool
    message: str
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    security_boundaries: tuple[str, ...] = field(default_factory=tuple)
