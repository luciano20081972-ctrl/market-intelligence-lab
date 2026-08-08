from __future__ import annotations

import hashlib
import importlib.metadata
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database.models import (
    CandidateFeatureSpec,
    ExperimentManifest,
    FactorExperiment,
    FactorExperimentFold,
    FactorStatistic,
    HypothesisEvidence,
    HypothesisMechanism,
    MultipleTestingResult,
    NegativeControlResult,
    ResearchBudget,
    ResearchHypothesis,
    ResearchOutcomeDefinition,
    ResearchPromotionEvent,
    RobustnessResult,
)
from packages.hypothesis.dsl import validate_feature_spec
from packages.hypothesis.lifecycle import (
    transition_hypothesis,
    validate_promotion_transition,
)
from packages.hypothesis.types import (
    HypothesisStatus,
    PromotionStage,
    ReasoningCandidate,
    TimePartition,
)
from packages.hypothesis.validation import partition_manifest, validate_partition


def checksum(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def dependency_versions() -> dict[str, str]:
    names = (
        "market-intelligence-lab",
        "numpy",
        "scipy",
        "statsmodels",
        "scikit-learn",
        "skfolio",
        "quantstats",
    )
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "unavailable"
    return versions


def create_hypothesis(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    subject_entity_id: uuid.UUID,
    candidate: ReasoningCandidate,
    hypothesis_type: str,
    origin: str,
    simulation_eligible_time: datetime,
    mechanism_confidence: Decimal = Decimal("0.70"),
    novelty_estimate: Decimal = Decimal("0.60"),
) -> ResearchHypothesis:
    payload = {
        "subject_entity_id": subject_entity_id,
        "title": candidate.title,
        "mechanism": candidate.mechanism,
        "feature": candidate.feature_specification,
        "falsification": candidate.falsification_criteria,
    }
    digest = checksum(payload)
    existing = session.scalar(
        select(ResearchHypothesis).where(
            ResearchHypothesis.workspace_id == workspace_id,
            ResearchHypothesis.checksum == digest,
        )
    )
    if existing is not None:
        return existing
    hypothesis = ResearchHypothesis(
        workspace_id=workspace_id,
        subject_entity_id=subject_entity_id,
        title=candidate.title,
        hypothesis_type=hypothesis_type,
        economic_rationale=candidate.rationale,
        machine_readable_mechanism=candidate.mechanism,
        expected_direction=str(candidate.feature_specification["expected_direction"]),
        expected_horizon=f"{candidate.feature_specification['lookback']} observations",
        required_evidence=list(candidate.required_evidence),
        required_graph_drivers=[
            str(item.get("driver", item.get("source", "external_driver")))
            for item in candidate.mechanism.get("graph_paths", [])
        ],
        required_datasets=list(candidate.feature_specification["required_datasets"]),
        proposed_outcome={"key": "future_operating_outcome", "horizon": 90},
        candidate_feature_specification=candidate.feature_specification,
        originating_method=origin,
        originating_model=None,
        falsification_criteria=list(candidate.falsification_criteria),
        mechanism_confidence=mechanism_confidence,
        novelty_estimate=novelty_estimate,
        assumptions=["Relationship evidence is not causal proof", "Point-in-time data only"],
        simulation_eligible_time=simulation_eligible_time,
        status=HypothesisStatus.DRAFT.value,
        version=1,
        checksum=digest,
    )
    session.add(hypothesis)
    session.flush()
    graph_paths = candidate.mechanism.get("graph_paths", [])
    session.add(
        HypothesisMechanism(
            hypothesis_id=hypothesis.id,
            version=1,
            source_driver=str(graph_paths[0].get("driver", "external driver"))
            if graph_paths
            else "external driver",
            affected_entity_id=subject_entity_id,
            relationship_path=list(graph_paths),
            expected_direction=hypothesis.expected_direction,
            lag_assumptions={"observations": candidate.feature_specification["lag"]},
            intermediate_mechanism=candidate.rationale,
            target_outcome=str(hypothesis.proposed_outcome["key"]),
            mechanism_confidence=mechanism_confidence,
        )
    )
    for evidence in candidate.required_evidence:
        session.add(
            HypothesisEvidence(
                hypothesis_id=hypothesis.id,
                evidence_record_id=None,
                stance=str(evidence.get("stance", evidence.get("type", "supporting"))),
                summary=str(
                    evidence.get("summary", evidence.get("requirement", "Required evidence"))
                ),
                source_reference=dict(evidence),
                simulation_eligible_time=simulation_eligible_time,
                confidence=Decimal("0.65"),
            )
        )
    return hypothesis


def create_candidate_feature_spec(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    hypothesis: ResearchHypothesis,
    specification: dict[str, Any],
) -> CandidateFeatureSpec:
    validate_feature_spec(specification)
    digest = checksum(specification)
    existing = session.scalar(
        select(CandidateFeatureSpec).where(
            CandidateFeatureSpec.workspace_id == workspace_id,
            CandidateFeatureSpec.checksum == digest,
        )
    )
    if existing is not None:
        return existing
    item = CandidateFeatureSpec(
        workspace_id=workspace_id,
        hypothesis_id=hypothesis.id,
        feature_key=str(specification["feature_key"]),
        required_datasets=list(specification["required_datasets"]),
        required_graph_paths=list(specification["required_graph_paths"]),
        transformations=list(specification["transformations"]),
        aggregation=dict(specification.get("aggregation", {})),
        lookback=int(specification["lookback"]),
        lag=int(specification["lag"]),
        weighting=dict(specification.get("weighting", {})),
        missing_data_policy=str(specification["missing_data_policy"]),
        normalization=str(specification["normalization"]),
        expected_direction=str(specification["expected_direction"]),
        required_output=str(specification.get("required_output", "numeric")),
        temporal_policy=dict(specification["temporal_policy"]),
        implementation_version=int(specification.get("implementation_version", 1)),
        generator=str(specification.get("generator", "deterministic")),
        checksum=digest,
    )
    session.add(item)
    session.flush()
    return item


def create_outcome_definition(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    key: str,
    outcome_type: str,
    horizon: int,
    benchmark: str | None = None,
) -> ResearchOutcomeDefinition:
    existing = session.scalar(
        select(ResearchOutcomeDefinition).where(
            ResearchOutcomeDefinition.workspace_id == workspace_id,
            ResearchOutcomeDefinition.key == key,
            ResearchOutcomeDefinition.version == 1,
        )
    )
    if existing is not None:
        return existing
    item = ResearchOutcomeDefinition(
        workspace_id=workspace_id,
        key=key,
        outcome_type=outcome_type,
        horizon=horizon,
        benchmark=benchmark,
        calculation={"method": "point_in_time_forward_change", "horizon": horizon},
        temporal_truth_policy={
            "labels_hidden_from_generator": True,
            "simulation_eligible_only": True,
            "final_test_sealed": True,
        },
        version=1,
    )
    session.add(item)
    session.flush()
    return item


def schedule_experiment(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    hypothesis: ResearchHypothesis,
    feature_spec: CandidateFeatureSpec,
    universe_version_id: uuid.UUID,
    feature_snapshot_id: uuid.UUID,
    outcome: ResearchOutcomeDefinition,
    partition: TimePartition,
    application_sha: str,
    seed: int,
) -> FactorExperiment:
    validate_partition(partition)
    protocol = {
        "partitions": partition_manifest(partition),
        "window": "expanding",
        "generator_final_test_access": False,
        "multiple_testing": "benjamini-hochberg",
    }
    payload = {
        "hypothesis": hypothesis.checksum,
        "feature_spec": feature_spec.checksum,
        "universe": universe_version_id,
        "snapshot": feature_snapshot_id,
        "outcome": outcome.id,
        "protocol": protocol,
        "seed": seed,
    }
    digest = checksum(payload)
    existing = session.scalar(
        select(FactorExperiment).where(
            FactorExperiment.workspace_id == workspace_id,
            FactorExperiment.checksum == digest,
        )
    )
    if existing is not None:
        return existing
    experiment = FactorExperiment(
        workspace_id=workspace_id,
        hypothesis_id=hypothesis.id,
        candidate_feature_spec_id=feature_spec.id,
        universe_version_id=universe_version_id,
        feature_snapshot_id=feature_snapshot_id,
        outcome_definition_id=outcome.id,
        graph_state={"authority": "MIL", "point_in_time": True},
        period_start=partition.train_start,
        period_end=partition.test_end,
        validation_protocol=protocol,
        cost_assumptions={"transaction_cost_bps": 5, "applies_to_return_outcomes": True},
        application_sha=application_sha,
        dependency_versions=dependency_versions(),
        seed=seed,
        status="SCHEDULED",
        checksum=digest,
    )
    session.add(experiment)
    session.flush()
    transition_hypothesis(hypothesis, HypothesisStatus.EVIDENCE_REQUIRED)
    transition_hypothesis(hypothesis, HypothesisStatus.READY_FOR_IMPLEMENTATION)
    transition_hypothesis(hypothesis, HypothesisStatus.IMPLEMENTED)
    transition_hypothesis(hypothesis, HypothesisStatus.TESTING)
    return experiment


def claim_factor_experiment(session: Session) -> FactorExperiment | None:
    statement = (
        select(FactorExperiment)
        .where(FactorExperiment.status == "SCHEDULED")
        .order_by(FactorExperiment.created_at, FactorExperiment.id)
        .limit(1)
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    item = session.scalar(statement)
    if item is not None:
        item.status = "RUNNING"
    return item


def add_fold(
    session: Session,
    *,
    experiment: FactorExperiment,
    fold_number: int,
    partition: TimePartition,
    observations: int,
    coverage: float,
    factor_statistics: dict[str, Any],
    model_statistics: dict[str, Any],
    warnings: list[str] | None = None,
    failures: list[str] | None = None,
) -> FactorExperimentFold:
    validate_partition(partition)
    fold = FactorExperimentFold(
        experiment_id=experiment.id,
        fold_number=fold_number,
        train_start=partition.train_start,
        train_end=partition.train_end,
        validation_start=partition.validation_start,
        validation_end=partition.validation_end,
        test_start=partition.test_start,
        test_end=partition.test_end,
        purge_observations=partition.purge_observations,
        embargo_observations=partition.embargo_observations,
        observations=observations,
        coverage=Decimal(str(coverage)),
        factor_statistics=factor_statistics,
        model_statistics=model_statistics,
        warnings=warnings or [],
        failures=failures or [],
    )
    session.add(fold)
    session.flush()
    for key, value in factor_statistics.items():
        if isinstance(value, (int, float)):
            session.add(
                FactorStatistic(
                    experiment_id=experiment.id,
                    fold_id=fold.id,
                    metric_key=key,
                    value=Decimal(str(value)),
                    segment="overall",
                    details={},
                )
            )
    return fold


def add_multiple_testing_results(
    session: Session,
    *,
    experiment: FactorExperiment,
    family: str,
    results: list[dict[str, float | bool | int | str]],
) -> None:
    for result in results:
        session.add(
            MultipleTestingResult(
                experiment_id=experiment.id,
                hypothesis_family=family,
                number_of_hypotheses=int(result["number_of_hypotheses"]),
                raw_p_value=Decimal(str(result["raw_p_value"])),
                adjusted_p_value=Decimal(str(result["adjusted_p_value"])),
                correction_method=str(result["correction_method"]),
                rejected_null=bool(result["rejected_null"]),
            )
        )


def record_promotion(
    session: Session,
    *,
    hypothesis: ResearchHypothesis,
    experiment: FactorExperiment | None,
    current: PromotionStage | str | None,
    target: PromotionStage | str,
    decision: str,
    reasons: list[str],
) -> ResearchPromotionEvent:
    requested = validate_promotion_transition(current, target)
    event = ResearchPromotionEvent(
        hypothesis_id=hypothesis.id,
        experiment_id=experiment.id if experiment else None,
        from_stage=str(current) if current else None,
        to_stage=requested.value,
        gate_version="research-promotion-v1",
        decision=decision,
        reasons=reasons,
        evidence={},
    )
    session.add(event)
    return event


def create_manifest(
    session: Session,
    *,
    experiment: FactorExperiment,
    hypothesis: ResearchHypothesis,
    feature_spec: CandidateFeatureSpec,
    alembic_revision: str,
) -> ExperimentManifest:
    payload = {
        "experiment": experiment.checksum,
        "hypothesis_version": hypothesis.version,
        "feature_spec": feature_spec.checksum,
        "validation": experiment.validation_protocol,
        "dependencies": experiment.dependency_versions,
    }
    item = ExperimentManifest(
        experiment_id=experiment.id,
        hypothesis_version=hypothesis.version,
        feature_spec={
            "feature_key": feature_spec.feature_key,
            "checksum": feature_spec.checksum,
            "transformations": feature_spec.transformations,
        },
        feature_snapshot_id=experiment.feature_snapshot_id,
        universe_version_id=experiment.universe_version_id,
        graph_reference_state=experiment.graph_state,
        source_manifests=[],
        software_sha=experiment.application_sha,
        alembic_revision=alembic_revision,
        dependency_versions=experiment.dependency_versions,
        model_config={"type": "factor_rank", "runtime_reasoning": False},
        validation_protocol=experiment.validation_protocol,
        random_seed=experiment.seed,
        time_boundaries=experiment.validation_protocol["partitions"],
        warnings=experiment.warnings,
        checksum=checksum(payload),
    )
    session.add(item)
    return item


def enforce_research_budget(
    session: Session,
    *,
    budget: ResearchBudget,
    requested: dict[str, int],
) -> dict[str, Any]:
    limits = budget.limits
    usage = {
        "hypotheses": session.scalar(select(func.count(ResearchHypothesis.id))) or 0,
        "experiments": session.scalar(select(func.count(FactorExperiment.id))) or 0,
        "walk_forward_folds": session.scalar(select(func.count(FactorExperimentFold.id))) or 0,
    }
    violations = [
        key
        for key, amount in requested.items()
        if usage.get(key, 0) + amount > int(limits.get(f"maximum_{key}", 10_000))
    ]
    return {
        "accepted": not violations,
        "violations": violations,
        "usage": usage,
        "requested": requested,
        "limits": limits,
    }


def record_robustness_matrix(
    session: Session,
    experiment: FactorExperiment,
    variants: list[dict[str, Any]],
) -> None:
    for variant in variants:
        payload = {"type": variant["type"], "parameters": variant["parameters"]}
        session.add(
            RobustnessResult(
                experiment_id=experiment.id,
                variant_type=str(variant["type"]),
                parameters=dict(variant["parameters"]),
                statistics=dict(variant["statistics"]),
                passed=bool(variant["passed"]),
                variant_checksum=checksum(payload),
            )
        )


def record_negative_controls(
    session: Session,
    experiment: FactorExperiment,
    controls: list[dict[str, Any]],
) -> bool:
    valid = True
    for control in controls:
        persistent = bool(control["persistent_power_detected"])
        valid = valid and not persistent
        session.add(
            NegativeControlResult(
                experiment_id=experiment.id,
                control_type=str(control["control_type"]),
                statistics=dict(control["statistics"]),
                persistent_power_detected=persistent,
                methodology_valid=not persistent,
                failure_reason=("NEGATIVE_CONTROL_PREDICTIVE_POWER" if persistent else None),
            )
        )
    return valid


def complete_experiment(
    experiment: FactorExperiment,
    hypothesis: ResearchHypothesis,
    *,
    accepted: bool,
    reasons: list[str],
) -> None:
    experiment.status = "COMPLETED" if accepted else "REJECTED"
    experiment.conclusion = "PROMISING" if accepted else "REJECTED"
    experiment.completed_at = datetime.now(UTC)
    experiment.warnings = list(experiment.warnings) + reasons
    transition_hypothesis(
        hypothesis, HypothesisStatus.PROMISING if accepted else HypothesisStatus.REJECTED
    )
