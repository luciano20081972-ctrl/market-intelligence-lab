from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from packages.database.models import (
    AblationResult,
    CandidateFeatureSpec,
    EconomicEntity,
    ExperimentManifest,
    FactorExperiment,
    FactorExperimentFold,
    FactorStatistic,
    HypothesisEvidence,
    HypothesisMechanism,
    MultipleTestingResult,
    NegativeControlResult,
    ResearchHypothesis,
    ResearchPromotionEvent,
    RobustnessResult,
)
from packages.hypothesis.engines import QlibResearchEngine, RDAgentResearchEngine
from packages.hypothesis.fixtures import seed_reference_hypothesis_research

router = APIRouter(tags=["hypothesis-research"])


def _workspace_id(session: Session) -> uuid.UUID:
    value = session.info.get("workspace_id")
    if not isinstance(value, uuid.UUID):
        raise HTTPException(status_code=403, detail="Workspace context is required")
    return value


def _hypothesis_response(item: ResearchHypothesis, company_name: str) -> dict[str, object]:
    return {
        "id": str(item.id),
        "subject_entity_id": str(item.subject_entity_id),
        "company_name": company_name,
        "title": item.title,
        "type": item.hypothesis_type,
        "economic_rationale": item.economic_rationale,
        "mechanism": item.machine_readable_mechanism,
        "expected_direction": item.expected_direction,
        "expected_horizon": item.expected_horizon,
        "required_evidence": item.required_evidence,
        "required_graph_drivers": item.required_graph_drivers,
        "required_datasets": item.required_datasets,
        "proposed_outcome": item.proposed_outcome,
        "candidate_feature_specification": item.candidate_feature_specification,
        "originating_method": item.originating_method,
        "falsification_criteria": item.falsification_criteria,
        "mechanism_confidence": str(item.mechanism_confidence),
        "novelty_estimate": str(item.novelty_estimate),
        "assumptions": item.assumptions,
        "simulation_eligible_time": item.simulation_eligible_time,
        "status": item.status,
        "version": item.version,
        "semantics": "research_hypothesis_not_investment_prediction",
    }


@router.get("/hypotheses")
def list_hypotheses(session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    rows = list(
        session.execute(
            select(ResearchHypothesis, EconomicEntity.canonical_name)
            .join(EconomicEntity, EconomicEntity.id == ResearchHypothesis.subject_entity_id)
            .where(ResearchHypothesis.workspace_id == workspace_id)
            .order_by(ResearchHypothesis.created_at, ResearchHypothesis.title)
        )
    )
    return {
        "items": [_hypothesis_response(item, name) for item, name in rows],
        "total": len(rows),
        "high_rejection_rate_expected": True,
    }


@router.get("/hypotheses/{hypothesis_id}")
def get_hypothesis(
    hypothesis_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    row = session.execute(
        select(ResearchHypothesis, EconomicEntity.canonical_name)
        .join(EconomicEntity, EconomicEntity.id == ResearchHypothesis.subject_entity_id)
        .where(
            ResearchHypothesis.id == hypothesis_id,
            ResearchHypothesis.workspace_id == workspace_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Hypothesis was not found")
    item, company_name = row
    response = _hypothesis_response(item, company_name)
    response["mechanisms"] = [
        {
            "id": str(mechanism.id),
            "source_driver": mechanism.source_driver,
            "relationship_path": mechanism.relationship_path,
            "expected_direction": mechanism.expected_direction,
            "lag_assumptions": mechanism.lag_assumptions,
            "intermediate_mechanism": mechanism.intermediate_mechanism,
            "target_outcome": mechanism.target_outcome,
            "terminology": "proposed mechanism; not causal proof",
        }
        for mechanism in session.scalars(
            select(HypothesisMechanism).where(HypothesisMechanism.hypothesis_id == item.id)
        )
    ]
    response["evidence"] = [
        {
            "id": str(evidence.id),
            "stance": evidence.stance,
            "summary": evidence.summary,
            "source_reference": evidence.source_reference,
        }
        for evidence in session.scalars(
            select(HypothesisEvidence).where(HypothesisEvidence.hypothesis_id == item.id)
        )
    ]
    response["feature_specs"] = [
        {
            "id": str(spec.id),
            "feature_key": spec.feature_key,
            "required_datasets": spec.required_datasets,
            "transformations": spec.transformations,
            "lookback": spec.lookback,
            "lag": spec.lag,
            "temporal_policy": spec.temporal_policy,
            "checksum": spec.checksum,
        }
        for spec in session.scalars(
            select(CandidateFeatureSpec).where(CandidateFeatureSpec.hypothesis_id == item.id)
        )
    ]
    return response


def _experiment_response(item: FactorExperiment) -> dict[str, object]:
    return {
        "id": str(item.id),
        "hypothesis_id": str(item.hypothesis_id),
        "candidate_feature_spec_id": str(item.candidate_feature_spec_id),
        "universe_version_id": str(item.universe_version_id),
        "feature_snapshot_id": str(item.feature_snapshot_id),
        "outcome_definition_id": str(item.outcome_definition_id),
        "status": item.status,
        "conclusion": item.conclusion,
        "period_start": item.period_start,
        "period_end": item.period_end,
        "validation_protocol": item.validation_protocol,
        "cost_assumptions": item.cost_assumptions,
        "dependency_versions": item.dependency_versions,
        "seed": item.seed,
        "warnings": item.warnings,
        "immutable": item.status in {"COMPLETED", "REJECTED"},
    }


def _experiment(session: Session, experiment_id: uuid.UUID) -> FactorExperiment:
    item = session.scalar(
        select(FactorExperiment).where(
            FactorExperiment.id == experiment_id,
            FactorExperiment.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Factor experiment was not found")
    return item


@router.get("/factor-experiments")
def list_experiments(session: Session = Depends(get_db)) -> dict[str, object]:
    items = list(
        session.scalars(
            select(FactorExperiment)
            .where(FactorExperiment.workspace_id == _workspace_id(session))
            .order_by(FactorExperiment.created_at)
        )
    )
    return {"items": [_experiment_response(item) for item in items], "total": len(items)}


@router.get("/factor-experiments/{experiment_id}")
def get_experiment(
    experiment_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    return _experiment_response(_experiment(session, experiment_id))


@router.get("/factor-experiments/{experiment_id}/folds")
def get_experiment_folds(
    experiment_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    item = _experiment(session, experiment_id)
    folds = list(
        session.scalars(
            select(FactorExperimentFold)
            .where(FactorExperimentFold.experiment_id == item.id)
            .order_by(FactorExperimentFold.fold_number)
        )
    )
    return {
        "items": [
            {
                "id": str(fold.id),
                "fold_number": fold.fold_number,
                "train": [fold.train_start, fold.train_end],
                "validation": [fold.validation_start, fold.validation_end],
                "final_out_of_sample_test": [fold.test_start, fold.test_end],
                "purge_observations": fold.purge_observations,
                "embargo_observations": fold.embargo_observations,
                "observations": fold.observations,
                "coverage": str(fold.coverage),
                "factor_statistics": fold.factor_statistics,
                "model_statistics": fold.model_statistics,
                "warnings": fold.warnings,
                "failures": fold.failures,
            }
            for fold in folds
        ],
        "total": len(folds),
        "failed_folds_are_retained": True,
    }


@router.get("/factor-experiments/{experiment_id}/statistics")
def get_statistics(
    experiment_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    item = _experiment(session, experiment_id)
    statistics = list(
        session.scalars(select(FactorStatistic).where(FactorStatistic.experiment_id == item.id))
    )
    corrections = list(
        session.scalars(
            select(MultipleTestingResult).where(MultipleTestingResult.experiment_id == item.id)
        )
    )
    return {
        "items": [
            {
                "metric_key": metric.metric_key,
                "value": str(metric.value) if metric.value is not None else None,
                "segment": metric.segment,
            }
            for metric in statistics
        ],
        "multiple_testing": [
            {
                "hypothesis_family": result.hypothesis_family,
                "number_of_hypotheses": result.number_of_hypotheses,
                "raw_p_value": str(result.raw_p_value),
                "adjusted_p_value": str(result.adjusted_p_value),
                "correction_method": result.correction_method,
                "rejected_null": result.rejected_null,
            }
            for result in corrections
        ],
        "raw_p_values_never_reported_alone": True,
    }


@router.get("/factor-experiments/{experiment_id}/robustness")
def get_robustness(
    experiment_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    item = _experiment(session, experiment_id)
    variants = list(
        session.scalars(select(RobustnessResult).where(RobustnessResult.experiment_id == item.id))
    )
    ablations = list(
        session.scalars(select(AblationResult).where(AblationResult.experiment_id == item.id))
    )
    controls = list(
        session.scalars(
            select(NegativeControlResult).where(NegativeControlResult.experiment_id == item.id)
        )
    )
    return {
        "variants": [
            {
                "type": result.variant_type,
                "parameters": result.parameters,
                "statistics": result.statistics,
                "passed": result.passed,
            }
            for result in variants
        ],
        "ablations": [
            {
                "component": result.component_key,
                "included_components": result.included_components,
                "statistics": result.statistics,
                "contribution": str(result.contribution),
            }
            for result in ablations
        ],
        "negative_controls": [
            {
                "control_type": result.control_type,
                "statistics": result.statistics,
                "persistent_power_detected": result.persistent_power_detected,
                "methodology_valid": result.methodology_valid,
            }
            for result in controls
        ],
    }


@router.get("/hypotheses/{hypothesis_id}/promotion-events")
def get_promotions(
    hypothesis_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    hypothesis = session.scalar(
        select(ResearchHypothesis).where(
            ResearchHypothesis.id == hypothesis_id,
            ResearchHypothesis.workspace_id == _workspace_id(session),
        )
    )
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Hypothesis was not found")
    events = list(
        session.scalars(
            select(ResearchPromotionEvent)
            .where(ResearchPromotionEvent.hypothesis_id == hypothesis.id)
            .order_by(ResearchPromotionEvent.created_at)
        )
    )
    return {
        "items": [
            {
                "from_stage": item.from_stage,
                "to_stage": item.to_stage,
                "decision": item.decision,
                "reasons": item.reasons,
                "gate_version": item.gate_version,
            }
            for item in events
        ],
        "total": len(events),
        "live_trading_status_exists": False,
    }


@router.get("/factor-experiments/{experiment_id}/manifest")
def get_manifest(experiment_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    item = _experiment(session, experiment_id)
    manifest = session.scalar(
        select(ExperimentManifest).where(ExperimentManifest.experiment_id == item.id)
    )
    if manifest is None:
        raise HTTPException(status_code=404, detail="Experiment manifest was not found")
    return {
        "id": str(manifest.id),
        "hypothesis_version": manifest.hypothesis_version,
        "feature_spec": manifest.feature_spec,
        "feature_snapshot_id": str(manifest.feature_snapshot_id),
        "universe_version_id": str(manifest.universe_version_id),
        "graph_reference_state": manifest.graph_reference_state,
        "source_manifests": manifest.source_manifests,
        "software_sha": manifest.software_sha,
        "alembic_revision": manifest.alembic_revision,
        "dependency_versions": manifest.dependency_versions,
        "validation_protocol": manifest.validation_protocol,
        "random_seed": manifest.random_seed,
        "time_boundaries": manifest.time_boundaries,
        "warnings": manifest.warnings,
        "checksum": manifest.checksum,
    }


@router.get("/research-engines/qlib")
def qlib_status() -> dict[str, object]:
    return asdict(QlibResearchEngine().status())


@router.get("/research-engines/rd-agent")
def rd_agent_status() -> dict[str, object]:
    return asdict(RDAgentResearchEngine().status())


@router.post("/hypotheses/reference-fixture", status_code=201)
def run_reference_fixture(session: Session = Depends(get_db)) -> dict[str, object]:
    result = seed_reference_hypothesis_research(session, _workspace_id(session))
    session.commit()
    return result
