from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.time import utc_now
from packages.database.models import (
    CandidateFeatureSpec,
    DivergenceDefinition,
    DivergenceEvent,
    ExperimentManifest,
    FactorExperiment,
    FactorExperimentFold,
    HypothesisMechanism,
    HypothesisMemoryDecision,
    MultipleTestingResult,
    NegativeControlResult,
    ResearchHypothesis,
    ResearchMemoryEntry,
    ResearchOutcomeDefinition,
    ResearchPromotionEvent,
    RobustnessResult,
)

CONVENTIONAL_BASELINE = {
    "version": "conventional-baseline-v1",
    "features": [
        "momentum",
        "size",
        "valuation",
        "revenue_growth",
        "profitability",
        "volatility",
        "sector",
        "market_exposure",
    ],
}


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _json_safe(value: Any) -> Any:
    """Normalize dated/decimal research artifacts for portable JSON persistence."""
    return json.loads(json.dumps(value, default=str))


def _decimal(value: float) -> Decimal:
    return Decimal(f"{max(-1.0, min(1.0, value)):.8f}")


def memory_as_of(
    session: Session, workspace_id: uuid.UUID, as_of: datetime
) -> list[ResearchMemoryEntry]:
    """Return only knowledge that was eligible at the requested historical time."""
    return list(
        session.scalars(
            select(ResearchMemoryEntry)
            .where(
                ResearchMemoryEntry.workspace_id == workspace_id,
                ResearchMemoryEntry.simulation_eligible_time <= as_of,
            )
            .order_by(ResearchMemoryEntry.simulation_eligible_time, ResearchMemoryEntry.id)
        )
    )


def divergence_as_of(
    session: Session, workspace_id: uuid.UUID, as_of: datetime
) -> list[DivergenceEvent]:
    return list(
        session.scalars(
            select(DivergenceEvent)
            .where(
                DivergenceEvent.workspace_id == workspace_id,
                DivergenceEvent.simulation_eligible_time <= as_of,
                DivergenceEvent.as_of_time <= as_of,
            )
            .order_by(DivergenceEvent.as_of_time, DivergenceEvent.id)
        )
    )


def create_memory_from_experiment(
    session: Session,
    experiment: FactorExperiment,
    *,
    applicability: dict[str, Any],
    regime_context: list[str],
) -> ResearchMemoryEntry:
    """Create an immutable lesson only after the relevant validation path completed."""
    if experiment.status not in {"COMPLETED", "REJECTED"} or experiment.completed_at is None:
        raise ValueError("only completed or rejected experiments can create research memory")
    hypothesis = session.get(ResearchHypothesis, experiment.hypothesis_id)
    feature = session.get(CandidateFeatureSpec, experiment.candidate_feature_spec_id)
    outcome = session.get(ResearchOutcomeDefinition, experiment.outcome_definition_id)
    if hypothesis is None or feature is None or outcome is None:
        raise ValueError("experiment research inputs are unavailable")
    folds = list(
        session.scalars(
            select(FactorExperimentFold)
            .where(FactorExperimentFold.experiment_id == experiment.id)
            .order_by(FactorExperimentFold.fold_number)
        )
    )
    if not folds or not any(
        fold.model_statistics.get("partition") == "FINAL_OUT_OF_SAMPLE" for fold in folds
    ):
        raise ValueError("TRAIN-only research cannot become research memory")
    mechanism = session.scalar(
        select(HypothesisMechanism).where(HypothesisMechanism.hypothesis_id == hypothesis.id)
    )
    manifest = session.scalar(
        select(ExperimentManifest).where(ExperimentManifest.experiment_id == experiment.id)
    )
    promotions = list(
        session.scalars(
            select(ResearchPromotionEvent).where(
                ResearchPromotionEvent.experiment_id == experiment.id
            )
        )
    )
    failure_reasons = [
        reason for event in promotions if event.to_stage == "REJECTED" for reason in event.reasons
    ]
    conclusion = "NEGATIVE" if hypothesis.status == "REJECTED" else "POSITIVE"
    eligible = experiment.completed_at
    mechanism_payload = (
        mechanism.relationship_path
        if mechanism is not None
        else hypothesis.machine_readable_mechanism
    )
    checksum = _digest(
        {
            "experiment": str(experiment.id),
            "hypothesis": hypothesis.checksum,
            "conclusion": conclusion,
            "eligible": eligible,
        }
    )
    existing = session.scalar(
        select(ResearchMemoryEntry).where(
            ResearchMemoryEntry.workspace_id == experiment.workspace_id,
            ResearchMemoryEntry.checksum == checksum,
        )
    )
    if existing is not None:
        return existing
    result = ResearchMemoryEntry(
        workspace_id=experiment.workspace_id,
        hypothesis_id=hypothesis.id,
        experiment_id=experiment.id,
        subject_entity_id=hypothesis.subject_entity_id,
        hypothesis_version=hypothesis.version,
        hypothesis_checksum=hypothesis.checksum,
        mechanism_checksum=_digest(mechanism_payload),
        feature_key=feature.feature_key,
        feature_version=feature.implementation_version,
        outcome_key=outcome.key,
        conclusion=conclusion,
        status="ACTIVE",
        graph_path=_json_safe(mechanism.relationship_path if mechanism is not None else []),
        datasets=list(hypothesis.required_datasets),
        feature_domains=list(applicability.get("feature_domains", [])),
        applicability=_json_safe(applicability),
        regime_context=regime_context,
        period_context=_json_safe(
            {
                "experiment": [experiment.period_start, experiment.period_end],
                "folds": [
                    {
                        "train": [fold.train_start, fold.train_end],
                        "validation": [fold.validation_start, fold.validation_end],
                        "final_oos": [fold.test_start, fold.test_end],
                    }
                    for fold in folds
                ],
            }
        ),
        result_summary=_json_safe(
            {
                "walk_forward": [fold.factor_statistics for fold in folds],
                "oos": [fold.model_statistics for fold in folds],
                "robustness": [
                    item.statistics
                    for item in session.scalars(
                        select(RobustnessResult).where(
                            RobustnessResult.experiment_id == experiment.id
                        )
                    )
                ],
                "multiple_testing": [
                    {"adjusted_p_value": str(item.adjusted_p_value), "passed": item.rejected_null}
                    for item in session.scalars(
                        select(MultipleTestingResult).where(
                            MultipleTestingResult.experiment_id == experiment.id
                        )
                    )
                ],
                "negative_controls": [
                    {
                        "type": item.control_type,
                        "methodology_valid": item.methodology_valid,
                        "persistent_power": item.persistent_power_detected,
                    }
                    for item in session.scalars(
                        select(NegativeControlResult).where(
                            NegativeControlResult.experiment_id == experiment.id
                        )
                    )
                ],
            }
        ),
        failure_reasons=failure_reasons,
        success_conditions=(
            ["validated OOS, robustness, and negative-control gates"]
            if conclusion == "POSITIVE"
            else []
        ),
        failure_conditions=failure_reasons,
        confidence=Decimal("0.850000") if conclusion == "POSITIVE" else Decimal("0.900000"),
        provenance=_json_safe(
            {
                "manifest_id": str(manifest.id) if manifest is not None else None,
                "experiment_checksum": experiment.checksum,
                "immutable_historical_record": True,
            }
        ),
        schema_version=1,
        first_learned_at=eligible,
        last_confirmed_at=eligible,
        simulation_eligible_time=eligible,
        checksum=checksum,
    )
    session.add(result)
    session.flush()
    return result


def classify_hypothesis(
    session: Session,
    hypothesis: ResearchHypothesis,
    *,
    feature_key: str,
    outcome_key: str,
    mechanism_checksum: str,
    override_authorized: bool = False,
) -> HypothesisMemoryDecision:
    matches = list(
        session.scalars(
            select(ResearchMemoryEntry).where(
                ResearchMemoryEntry.workspace_id == hypothesis.workspace_id,
                ResearchMemoryEntry.mechanism_checksum == mechanism_checksum,
                ResearchMemoryEntry.feature_key == feature_key,
                ResearchMemoryEntry.outcome_key == outcome_key,
                ResearchMemoryEntry.status.in_(["ACTIVE", "WEAK", "CONTRADICTED"]),
            )
        )
    )
    negative = [item for item in matches if item.conclusion == "NEGATIVE"]
    positive = [item for item in matches if item.conclusion == "POSITIVE"]
    if negative and positive:
        classification = "CONTRADICTED"
    elif negative:
        classification = "KNOWN_FAILURE"
    elif positive:
        classification = "KNOWN_SUCCESS"
    else:
        classification = "NEW"
    suppressed = classification in {"KNOWN_FAILURE", "DUPLICATE"} and not override_authorized
    decision = HypothesisMemoryDecision(
        workspace_id=hypothesis.workspace_id,
        hypothesis_id=hypothesis.id,
        classification=classification,
        matched_memory_ids=[str(item.id) for item in matches],
        decision="SUPPRESSED" if suppressed else "SCHEDULE_ALLOWED",
        reason=(
            "A materially equivalent robust rejection is already recorded"
            if suppressed
            else "No automatic suppression applies; normal validation gates remain required"
        ),
        override_authorized=override_authorized,
        policy_version="memory-policy-v1",
    )
    session.add(decision)
    session.flush()
    return decision


def _rank(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average = (index + end - 1) / 2 + 1
        for offset in range(index, end):
            ranks[ordered[offset][0]] = average
        index = end
    return ranks


def pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 3:
        raise ValueError("correlation requires equally sized samples with at least three values")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True))
    left_scale = math.sqrt(sum((x - left_mean) ** 2 for x in left))
    right_scale = math.sqrt(sum((y - right_mean) ** 2 for y in right))
    if left_scale == 0 or right_scale == 0:
        return 0.0
    return numerator / (left_scale * right_scale)


def spearman(left: Sequence[float], right: Sequence[float]) -> float:
    return pearson(_rank(left), _rank(right))


def residualize(candidate: Sequence[float], baseline: Sequence[float]) -> list[float]:
    if len(candidate) != len(baseline) or len(candidate) < 3:
        raise ValueError("residualization requires equal samples")
    baseline_mean = sum(baseline) / len(baseline)
    candidate_mean = sum(candidate) / len(candidate)
    variance = sum((value - baseline_mean) ** 2 for value in baseline)
    slope = (
        sum(
            (x - baseline_mean) * (y - candidate_mean)
            for x, y in zip(baseline, candidate, strict=True)
        )
        / variance
        if variance
        else 0.0
    )
    intercept = candidate_mean - slope * baseline_mean
    return [y - (intercept + slope * x) for x, y in zip(baseline, candidate, strict=True)]


def independence_components(
    candidate: Sequence[float], baseline: Sequence[float], outcome: Sequence[float]
) -> dict[str, float]:
    candidate_ic = spearman(candidate, outcome)
    baseline_ic = spearman(baseline, outcome)
    correlation = pearson(candidate, baseline)
    rank_correlation = spearman(candidate, baseline)
    residuals = residualize(candidate, baseline)
    residual_ic = spearman(residuals, outcome)
    incremental = max(0.0, abs(candidate_ic) - abs(baseline_ic))
    redundancy = min(1.0, (abs(correlation) + abs(rank_correlation)) / 2)
    independent_score = (
        0.35 * min(1.0, abs(residual_ic))
        + 0.30 * min(1.0, incremental)
        + 0.25 * (1 - redundancy)
        + 0.10 * min(1.0, abs(candidate_ic))
    )
    return {
        "pearson_to_baseline": correlation,
        "spearman_to_baseline": rank_correlation,
        "partial_correlation": residual_ic,
        "residual_contribution": abs(residual_ic),
        "candidate_rank_ic": candidate_ic,
        "baseline_rank_ic": baseline_ic,
        "incremental_rank_ic": incremental,
        "redundancy_score": redundancy,
        "independent_information_score": independent_score,
    }


def detect_divergence(
    session: Session,
    definition: DivergenceDefinition,
    *,
    subject_entity_id: uuid.UUID,
    as_of_time: datetime,
    domain_values: dict[str, float],
    persistence_periods: int,
    historical_analogues: list[dict[str, Any]] | None = None,
) -> DivergenceEvent | None:
    domains = list(definition.domains)
    if any(domain not in domain_values for domain in domains):
        return None
    values = [max(-1.0, min(1.0, domain_values[domain])) for domain in domains]
    spread = max(values) - min(values)
    pairwise = sum(
        abs(values[left] - values[right])
        for left in range(len(values))
        for right in range(left + 1, len(values))
    ) / max(1, len(values) * (len(values) - 1) / 2)
    sign_disagreement = len({value >= 0 for value in values}) > 1
    threshold = float(definition.rules.get("minimum_disagreement_magnitude", 1.0))
    minimum_persistence = int(definition.rules.get("minimum_persistence", 1))
    if spread < threshold or persistence_periods < minimum_persistence or not sign_disagreement:
        return None
    payload = {
        "definition": str(definition.id),
        "subject": str(subject_entity_id),
        "as_of": as_of_time,
        "values": domain_values,
    }
    checksum = _digest(payload)
    existing = session.scalar(
        select(DivergenceEvent).where(
            DivergenceEvent.workspace_id == definition.workspace_id,
            DivergenceEvent.checksum == checksum,
        )
    )
    if existing is not None:
        return existing
    result = DivergenceEvent(
        workspace_id=definition.workspace_id,
        definition_id=definition.id,
        subject_entity_id=subject_entity_id,
        research_candidate_id=None,
        feature_snapshot_id=None,
        as_of_time=as_of_time,
        domain_values={
            domain: {"raw": domain_values[domain], "normalized": values[index]}
            for index, domain in enumerate(domains)
        },
        magnitude_components={
            "max_minus_min": spread,
            "mean_pairwise_disagreement": pairwise,
            "sign_disagreement": sign_disagreement,
            "methodology": "transparent-domain-dispersion-v1",
        },
        disagreement_magnitude=Decimal(f"{spread:.8f}"),
        persistence_periods=persistence_periods,
        data_completeness=Decimal("1.000000"),
        evidence={"temporal_truth": "all inputs eligible at as_of_time"},
        historical_analogues=historical_analogues or [],
        confidence=Decimal("0.880000"),
        research_priority=Decimal("0.900000"),
        status="DETECTED",
        simulation_eligible_time=as_of_time,
        checksum=checksum,
    )
    session.add(result)
    session.flush()
    return result


def weaken_memory(memory: ResearchMemoryEntry, reason: str, at: datetime | None = None) -> None:
    if memory.status not in {"ACTIVE", "WEAK"}:
        raise ValueError("only active or weak memory can be weakened")
    memory.status = "WEAK"
    memory.provenance = {
        **memory.provenance,
        "latest_revalidation": {
            "state": "WEAK",
            "reason": reason,
            "at": (at or utc_now()).isoformat(),
        },
    }


def revalidate_memory(
    memory: ResearchMemoryEntry, evidence: str, at: datetime | None = None
) -> None:
    if memory.status != "WEAK":
        raise ValueError("only weak memory can be revalidated")
    memory.status = "ACTIVE"
    memory.last_confirmed_at = at or utc_now()
    memory.provenance = {
        **memory.provenance,
        "latest_revalidation": {
            "state": "ACTIVE",
            "evidence": evidence,
            "at": (at or utc_now()).isoformat(),
        },
    }


def score_decimals(components: dict[str, float]) -> dict[str, Decimal]:
    return {key: _decimal(value) for key, value in components.items()}
