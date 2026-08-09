from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import (
    AblationResult,
    EconomicEntity,
    FactorExperiment,
    FeatureSnapshot,
    ResearchBudget,
    ResearchHypothesis,
    ResearchUniverseVersion,
)
from packages.hypothesis.lifecycle import transition_hypothesis
from packages.hypothesis.reasoning import DeterministicReasoningProvider
from packages.hypothesis.service import (
    add_fold,
    add_multiple_testing_results,
    complete_experiment,
    create_candidate_feature_spec,
    create_hypothesis,
    create_manifest,
    create_outcome_definition,
    enforce_research_budget,
    record_negative_controls,
    record_promotion,
    record_robustness_matrix,
    schedule_experiment,
)
from packages.hypothesis.types import HypothesisStatus, PromotionStage, ReasoningRequest
from packages.hypothesis.validation import (
    adjust_p_values,
    deterministic_negative_controls,
    expanding_walk_forward,
    factor_statistics,
    incremental_information_test,
)
from packages.research.fixtures import REFERENCE_AS_OF, seed_reference_research

APPLICATION_SHA = "fixture-v0.10"
MIGRATION_HEAD = "3b2f6c7d8e90"


def _companies_by_archetype(session: Session) -> dict[str, EconomicEntity]:
    result: dict[str, EconomicEntity] = {}
    for company in session.scalars(select(EconomicEntity).order_by(EconomicEntity.canonical_name)):
        archetype = str(company.provenance_json.get("archetype", ""))
        if archetype and archetype not in result:
            result[archetype] = company
    required = {"semiconductor", "airline", "agriculture"}
    if result.keys() < required:
        raise RuntimeError("v0.9 reference archetypes are unavailable")
    return result


def _graph_path(archetype: str) -> dict[str, Any]:
    paths = {
        "semiconductor": {
            "driver": "EIA electricity prices",
            "path": ["EnergyMarket", "Region", "Facility", "Company", "operating costs", "margin"],
            "terminology": "hypothesized transmission path",
        },
        "airline": {
            "driver": "jet fuel and severe weather",
            "path": ["EnergyMarket", "AirportRegion", "RouteNetwork", "Airline", "operating costs"],
            "terminology": "evidence-backed relationship",
        },
        "agriculture": {
            "driver": "water stress and fertilizer energy",
            "path": ["WeatherRegion", "WaterBasin", "CropRegion", "Producer", "yield", "revenue"],
            "terminology": "proposed mechanism",
        },
    }
    return paths[archetype]


def _synthetic_evaluation(archetype: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    generator = np.random.default_rng(seed)
    candidate = generator.normal(0, 1, 180)
    strength = {"semiconductor": 0.16, "airline": 0.10, "agriculture": 0.0}[archetype]
    outcome = strength * candidate + generator.normal(0, 1, 180)
    return candidate, outcome


def seed_reference_hypothesis_research(
    session: Session,
    workspace_id: uuid.UUID,
    *,
    application_sha: str = APPLICATION_SHA,
    migration_head: str = MIGRATION_HEAD,
) -> dict[str, Any]:
    base = seed_reference_research(
        session,
        workspace_id,
        application_sha=application_sha,
        migration_head="2f9e39afd435",
    )
    existing = list(
        session.scalars(
            select(ResearchHypothesis).where(ResearchHypothesis.workspace_id == workspace_id)
        )
    )
    if existing:
        existing_experiments = list(session.scalars(select(FactorExperiment)))
        return _fixture_result(base, existing, existing_experiments)

    companies = _companies_by_archetype(session)
    snapshot = session.scalar(select(FeatureSnapshot).order_by(FeatureSnapshot.created_at.desc()))
    universe_version = session.scalar(
        select(ResearchUniverseVersion).order_by(ResearchUniverseVersion.version.desc())
    )
    budget = session.scalar(
        select(ResearchBudget).where(
            ResearchBudget.workspace_id == workspace_id,
            ResearchBudget.level == "LEVEL_4",
        )
    )
    if snapshot is None or universe_version is None or budget is None:
        raise RuntimeError("v0.9 research snapshot, universe, or Level-4 budget is unavailable")
    budget.limits = {
        **budget.limits,
        "maximum_hypotheses": 30,
        "maximum_experiments": 30,
        "maximum_walk_forward_folds": 100,
        "maximum_qlib_runs": 3,
        "maximum_rd_agent_runs": 0,
        "maximum_ai_tokens": 0,
        "maximum_runtime_model_requests": 0,
    }
    decision = enforce_research_budget(
        session,
        budget=budget,
        requested={"hypotheses": 3, "experiments": 3, "walk_forward_folds": 9},
    )
    if not decision["accepted"]:
        raise RuntimeError("reference research budget rejected the bounded fixture")

    provider = DeterministicReasoningProvider()
    hypotheses: list[ResearchHypothesis] = []
    experiments: list[FactorExperiment] = []
    for index, archetype in enumerate(("semiconductor", "airline", "agriculture")):
        company = companies[archetype]
        graph_path = _graph_path(archetype)
        candidate = provider.generate_hypotheses(
            ReasoningRequest(
                subject={
                    "entity_id": str(company.id),
                    "name": company.canonical_name,
                    "archetype": archetype,
                },
                graph_paths=(graph_path,),
                evidence=(
                    {
                        "stance": "supporting",
                        "summary": "Point-in-time source and graph relationship evidence required",
                    },
                    {
                        "stance": "contradicting",
                        "summary": "Alternative operating mechanism must be evaluated",
                    },
                ),
                datasets=tuple(),
                maximum_hypotheses=1,
            )
        )[0]
        hypothesis = create_hypothesis(
            session,
            workspace_id=workspace_id,
            subject_entity_id=company.id,
            candidate=candidate,
            hypothesis_type="company_specific_economic_mechanism",
            origin="deterministic_graph_derived",
            simulation_eligible_time=REFERENCE_AS_OF,
            mechanism_confidence=Decimal(("0.78", "0.74", "0.69")[index]),
            novelty_estimate=Decimal(("0.71", "0.67", "0.64")[index]),
        )
        feature_spec = create_candidate_feature_spec(
            session,
            workspace_id=workspace_id,
            hypothesis=hypothesis,
            specification=candidate.feature_specification,
        )
        outcome_parameters = {
            "semiconductor": ("future_operating_margin_change_90d", "future_margin_change", None),
            "airline": ("future_excess_return_30d", "future_excess_return", "sector_airlines"),
            "agriculture": ("future_revenue_growth_120d", "future_revenue_growth", None),
        }[archetype]
        outcome = create_outcome_definition(
            session,
            workspace_id=workspace_id,
            key=outcome_parameters[0],
            outcome_type=outcome_parameters[1],
            horizon=(90, 30, 120)[index],
            benchmark=outcome_parameters[2],
        )
        folds = expanding_walk_forward(
            start=REFERENCE_AS_OF - timedelta(days=1095),
            train_days=540,
            validation_days=90,
            test_days=90,
            folds=3,
            purge_days=5,
            embargo_days=5,
        )
        experiment = schedule_experiment(
            session,
            workspace_id=workspace_id,
            hypothesis=hypothesis,
            feature_spec=feature_spec,
            universe_version_id=universe_version.id,
            feature_snapshot_id=snapshot.id,
            outcome=outcome,
            partition=folds[0],
            application_sha=application_sha,
            seed=10_000 + index,
        )
        experiment.status = "RUNNING"
        candidate_values, outcome_values = _synthetic_evaluation(archetype, 10_000 + index)
        fold_ics: list[float] = []
        for fold_number, fold in enumerate(folds):
            start = fold_number * 60
            metrics = factor_statistics(
                candidate_values[start : start + 60], outcome_values[start : start + 60]
            )
            fold_ics.append(metrics.spearman_ic)
            baseline = np.column_stack(
                [
                    np.roll(candidate_values[start : start + 60], 3),
                    np.linspace(-1, 1, 60),
                ]
            )
            incremental = incremental_information_test(
                baseline,
                candidate_values[start : start + 60],
                outcome_values[start : start + 60],
                40,
            )
            add_fold(
                session,
                experiment=experiment,
                fold_number=fold_number,
                partition=fold,
                observations=60,
                coverage=metrics.coverage,
                factor_statistics=asdict(metrics),
                model_statistics={
                    **incremental,
                    "partition": "FINAL_OUT_OF_SAMPLE",
                    "baseline": "momentum+growth+profitability+sector",
                },
                warnings=list(metrics.warnings),
            )
        raw_p_values = {
            "semiconductor": [0.004, 0.016, 0.028],
            "airline": [0.012, 0.031, 0.049],
            "agriculture": [0.21, 0.48, 0.77],
        }[archetype]
        corrections = adjust_p_values(raw_p_values, method="benjamini-hochberg")
        add_multiple_testing_results(
            session,
            experiment=experiment,
            family=f"{archetype}-fixture-family",
            results=corrections,
        )
        accepted = archetype != "agriculture" and any(
            bool(item["rejected_null"]) for item in corrections
        )
        record_robustness_matrix(
            session,
            experiment,
            [
                {
                    "type": variant,
                    "parameters": {"variant": variant},
                    "statistics": {"mean_rank_ic": float(np.mean(fold_ics))},
                    "passed": accepted,
                }
                for variant in (
                    "alternate_lookback",
                    "alternate_lag",
                    "different_period",
                    "alternate_normalization",
                    "missing_data_policy",
                    "winsorization",
                    "transaction_costs",
                )
            ],
        )
        controls = deterministic_negative_controls(candidate_values, 900 + index)
        controls_valid = record_negative_controls(
            session,
            experiment,
            [
                {
                    "control_type": key,
                    "statistics": {"rank_ic": 0.0, "observations": len(values)},
                    "persistent_power_detected": False,
                }
                for key, values in controls.items()
            ],
        )
        for component, contribution in (
            ("external_driver", "0.012"),
            ("geographic_exposure", "0.008"),
            ("combined", "0.017"),
        ):
            session.add(
                AblationResult(
                    experiment_id=experiment.id,
                    component_key=component,
                    included_components=[component],
                    statistics={"rank_ic": contribution},
                    contribution=Decimal(contribution),
                )
            )
        current: PromotionStage | None = None
        last_successful = PromotionStage.BACKTESTED
        for stage in (
            PromotionStage.DRAFT,
            PromotionStage.EVIDENCE_CHECKED,
            PromotionStage.IMPLEMENTED,
            PromotionStage.LEAKAGE_CHECKED,
            PromotionStage.BACKTESTED,
        ):
            record_promotion(
                session,
                hypothesis=hypothesis,
                experiment=experiment,
                current=current,
                target=stage,
                decision="passed",
                reasons=["deterministic fixture gate passed"],
            )
            current = stage
        if accepted and controls_valid:
            for stage in (
                PromotionStage.WALK_FORWARD_PASSED,
                PromotionStage.ROBUSTNESS_PASSED,
                PromotionStage.OOS_PASSED,
                PromotionStage.PAPER_ELIGIBLE,
            ):
                record_promotion(
                    session,
                    hypothesis=hypothesis,
                    experiment=experiment,
                    current=current,
                    target=stage,
                    decision="passed",
                    reasons=["fixture result passed configured research gate"],
                )
                current = stage
            last_successful = PromotionStage.PAPER_ELIGIBLE
        else:
            record_promotion(
                session,
                hypothesis=hypothesis,
                experiment=experiment,
                current=current,
                target=PromotionStage.REJECTED,
                decision="rejected",
                reasons=[
                    "no out-of-sample persistence",
                    "multiple-testing correction not significant",
                    "no incremental information after conventional baselines",
                ],
            )
        complete_experiment(
            experiment,
            hypothesis,
            accepted=accepted,
            reasons=(
                ["RESEARCH_RESULT_NOT_INVESTMENT_RECOMMENDATION"]
                if accepted
                else ["EXPECTED_SCIENTIFIC_REJECTION", f"last_gate={last_successful.value}"]
            ),
        )
        if accepted:
            if hypothesis.status == "PROMISING":
                transition_hypothesis(hypothesis, HypothesisStatus.VALIDATED)
        create_manifest(
            session,
            experiment=experiment,
            hypothesis=hypothesis,
            feature_spec=feature_spec,
            alembic_revision=migration_head,
        )
        hypotheses.append(hypothesis)
        experiments.append(experiment)
    session.flush()
    return _fixture_result(base, hypotheses, experiments)


def _fixture_result(
    base: dict[str, Any],
    hypotheses: list[ResearchHypothesis],
    experiments: list[FactorExperiment],
) -> dict[str, Any]:
    return {
        **base,
        "hypothesis_count": len(hypotheses),
        "experiment_count": len(experiments),
        "fold_count": len(experiments) * 3,
        "hypothesis_ids": [str(item.id) for item in hypotheses],
        "experiment_ids": [str(item.id) for item in experiments],
        "archetypes": [
            {
                "title": item.title,
                "status": item.status,
                "subject_entity_id": str(item.subject_entity_id),
            }
            for item in hypotheses
        ],
        "rejected_hypotheses": sum(item.status == "REJECTED" for item in hypotheses),
        "negative_controls": len(experiments) * 4,
        "runtime_model_requests": 0,
        "ai_tokens": 0,
        "scientific_semantics": "hypothesis_research_not_investment_prediction",
    }
