from __future__ import annotations

from collections.abc import Mapping

from packages.database.models import FactorExperiment, ResearchHypothesis
from packages.hypothesis.types import HypothesisStatus, PromotionStage

HYPOTHESIS_TRANSITIONS: Mapping[HypothesisStatus, frozenset[HypothesisStatus]] = {
    HypothesisStatus.DRAFT: frozenset(
        {HypothesisStatus.EVIDENCE_REQUIRED, HypothesisStatus.READY_FOR_IMPLEMENTATION}
    ),
    HypothesisStatus.EVIDENCE_REQUIRED: frozenset(
        {HypothesisStatus.READY_FOR_IMPLEMENTATION, HypothesisStatus.REJECTED}
    ),
    HypothesisStatus.READY_FOR_IMPLEMENTATION: frozenset(
        {HypothesisStatus.IMPLEMENTED, HypothesisStatus.REJECTED}
    ),
    HypothesisStatus.IMPLEMENTED: frozenset({HypothesisStatus.TESTING, HypothesisStatus.REJECTED}),
    HypothesisStatus.TESTING: frozenset({HypothesisStatus.REJECTED, HypothesisStatus.PROMISING}),
    HypothesisStatus.PROMISING: frozenset(
        {HypothesisStatus.VALIDATED, HypothesisStatus.REJECTED, HypothesisStatus.RETIRED}
    ),
    HypothesisStatus.VALIDATED: frozenset({HypothesisStatus.RETIRED}),
    HypothesisStatus.REJECTED: frozenset({HypothesisStatus.RETIRED}),
    HypothesisStatus.RETIRED: frozenset(),
}

PROMOTION_ORDER = (
    PromotionStage.DRAFT,
    PromotionStage.EVIDENCE_CHECKED,
    PromotionStage.IMPLEMENTED,
    PromotionStage.LEAKAGE_CHECKED,
    PromotionStage.BACKTESTED,
    PromotionStage.WALK_FORWARD_PASSED,
    PromotionStage.ROBUSTNESS_PASSED,
    PromotionStage.OOS_PASSED,
    PromotionStage.PAPER_ELIGIBLE,
)


def transition_hypothesis(
    hypothesis: ResearchHypothesis, target: HypothesisStatus | str
) -> ResearchHypothesis:
    current = HypothesisStatus(hypothesis.status)
    requested = HypothesisStatus(target)
    if requested not in HYPOTHESIS_TRANSITIONS[current]:
        raise ValueError(f"invalid hypothesis transition: {current.value} -> {requested.value}")
    hypothesis.status = requested.value
    return hypothesis


def validate_promotion_transition(
    current: PromotionStage | str | None, target: PromotionStage | str
) -> PromotionStage:
    requested = PromotionStage(target)
    if requested is PromotionStage.REJECTED:
        return requested
    if current is None:
        if requested is not PromotionStage.DRAFT:
            raise ValueError("promotion must begin at DRAFT")
        return requested
    existing = PromotionStage(current)
    if existing is PromotionStage.REJECTED:
        raise ValueError("rejected research cannot be promoted")
    expected_index = PROMOTION_ORDER.index(existing) + 1
    if expected_index >= len(PROMOTION_ORDER) or PROMOTION_ORDER[expected_index] is not requested:
        raise ValueError(f"invalid promotion transition: {existing.value} -> {requested.value}")
    return requested


def assert_experiment_mutable(experiment: FactorExperiment) -> None:
    if experiment.status in {"COMPLETED", "REJECTED"}:
        raise ValueError("completed experiments are immutable")
