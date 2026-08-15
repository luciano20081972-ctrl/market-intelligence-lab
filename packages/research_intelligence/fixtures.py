from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import (
    DivergenceDefinition,
    EconomicEntity,
    FactorCluster,
    FactorExperiment,
    FactorRedundancyResult,
    InformationValueRecord,
    ResearchContradiction,
    ResearchHypothesis,
    ResearchMethodReliability,
    ResearchOutcomeAttribution,
    ResearchRegimeAssignment,
    ResearchRegimeDefinition,
    SignalIndependenceAnalysis,
)
from packages.hypothesis.fixtures import seed_reference_hypothesis_research
from packages.research_intelligence.service import (
    CONVENTIONAL_BASELINE,
    classify_hypothesis,
    create_memory_from_experiment,
    detect_divergence,
    independence_components,
)

REFERENCE_INTELLIGENCE_AS_OF = datetime(2026, 2, 15, 12, tzinfo=UTC)


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _analysis_fixture(kind: str) -> tuple[list[float], list[float], list[float]]:
    baseline = [float(index) for index in range(1, 41)]
    if kind == "redundant":
        outcome = [value + ((index % 5) - 2) * 0.7 for index, value in enumerate(baseline)]
        candidate = [
            value * 1.02 + ((index % 3) - 1) * 0.05 for index, value in enumerate(baseline)
        ]
    else:
        candidate = [float((index * 17) % 41) for index in range(1, 41)]
        outcome = [
            0.70 * candidate[index] + 0.30 * baseline[index] for index in range(len(baseline))
        ]
    return candidate, baseline, outcome


def seed_reference_research_intelligence(
    session: Session, workspace_id: uuid.UUID
) -> dict[str, Any]:
    existing = list(
        session.scalars(
            select(SignalIndependenceAnalysis).where(
                SignalIndependenceAnalysis.workspace_id == workspace_id
            )
        )
    )
    if existing:
        return _summary(session, workspace_id)

    seed_reference_hypothesis_research(session, workspace_id)
    rows = list(
        session.execute(
            select(FactorExperiment, ResearchHypothesis, EconomicEntity)
            .join(ResearchHypothesis, ResearchHypothesis.id == FactorExperiment.hypothesis_id)
            .join(EconomicEntity, EconomicEntity.id == ResearchHypothesis.subject_entity_id)
            .where(FactorExperiment.workspace_id == workspace_id)
            .order_by(EconomicEntity.canonical_name)
        )
    )
    if len(rows) < 3:
        raise RuntimeError("v0.10 reference experiments are required")
    memories = []
    row_by_archetype: dict[str, tuple[FactorExperiment, ResearchHypothesis, EconomicEntity]] = {}
    for experiment, hypothesis, entity in rows:
        archetype = (
            "agriculture"
            if "harvest" in entity.canonical_name.lower()
            else "airline"
            if "meridian" in entity.canonical_name.lower()
            else "semiconductor"
        )
        row_by_archetype[archetype] = (experiment, hypothesis, entity)
        business_model = {
            "semiconductor": "electricity-intensive semiconductor manufacturer",
            "airline": "network airline operator",
            "agriculture": "diversified agricultural cooperative",
        }[archetype]
        memory = create_memory_from_experiment(
            session,
            experiment,
            applicability={
                "company": entity.canonical_name,
                "business_model": business_model,
                "sector": archetype,
                "industry": business_model,
                "geography": "United States",
                "horizon": hypothesis.expected_horizon,
                "feature_configuration": hypothesis.candidate_feature_specification,
                "graph_configuration": hypothesis.required_graph_drivers,
                "data_quality_requirements": ["point-in-time eligible", "complete coverage"],
                "dataset_availability": hypothesis.required_datasets,
                "outcome": hypothesis.proposed_outcome,
                "universe_characteristics": "deterministic reference research universe",
                "feature_domains": [archetype, "external_driver"],
                "version": 1,
            },
            regime_context=["high inflation", "rising rates"],
        )
        memories.append(memory)

    regime = ResearchRegimeDefinition(
        workspace_id=workspace_id,
        key="inflation-rates-volatility",
        label="Point-in-time inflation, rates, and volatility context",
        method={
            "type": "deterministic_thresholds",
            "features": ["inflation_yoy", "policy_rate_change", "market_volatility"],
            "thresholds": {"high_inflation": 0.03, "rising_rates": 0.0, "high_volatility": 0.25},
            "no_future_data": True,
        },
        version=1,
    )
    session.add(regime)
    session.flush()
    for _, _, entity in rows:
        session.add(
            ResearchRegimeAssignment(
                workspace_id=workspace_id,
                definition_id=regime.id,
                subject_entity_id=entity.id,
                as_of_time=REFERENCE_INTELLIGENCE_AS_OF,
                active=True,
                evidence={"high_inflation": 0.041, "policy_rate_change": 0.0075},
                simulation_eligible_time=REFERENCE_INTELLIGENCE_AS_OF,
            )
        )

    semi_experiment, _, _ = row_by_archetype["semiconductor"]
    airline_experiment, _, airline_entity = row_by_archetype["airline"]
    for label, experiment, kind in (
        ("conventional-overlap-factor", semi_experiment, "redundant"),
        ("external-driver-independent-factor", airline_experiment, "independent"),
    ):
        candidate, baseline, outcome = _analysis_fixture(kind)
        components = independence_components(candidate, baseline, outcome)
        checksum = _digest({"factor": label, "components": components})
        session.add(
            SignalIndependenceAnalysis(
                workspace_id=workspace_id,
                experiment_id=experiment.id,
                factor_key=label,
                baseline_version=CONVENTIONAL_BASELINE["version"],
                methodology_version="signal-independence-v1",
                predictive_strength=Decimal(f"{abs(components['candidate_rank_ic']):.8f}"),
                independent_contribution=Decimal(f"{abs(components['partial_correlation']):.8f}"),
                redundancy_score=Decimal(f"{components['redundancy_score']:.8f}"),
                independent_information_score=Decimal(
                    f"{components['independent_information_score']:.8f}"
                ),
                components={
                    **components,
                    "incremental_predictive_error_reduction": (
                        0.01 if kind == "redundant" else 0.18
                    ),
                    "sector_neutral_contribution": (0.03 if kind == "redundant" else 0.31),
                    "regime_specific_contribution": {"high_inflation": 0.22},
                    "stability": 0.82,
                },
                formula={
                    "version": "independent-information-score-v1",
                    "weights": {
                        "residual_contribution": 0.35,
                        "incremental_rank_ic": 0.30,
                        "low_redundancy": 0.25,
                        "predictive_strength": 0.10,
                    },
                    "semantics": "independent_information_not_probability_of_profit",
                },
                segments={"sector": kind, "regime": "high inflation"},
                as_of_time=REFERENCE_INTELLIGENCE_AS_OF,
                simulation_eligible_time=REFERENCE_INTELLIGENCE_AS_OF,
                checksum=checksum,
            )
        )
        session.add(
            FactorRedundancyResult(
                workspace_id=workspace_id,
                factor_a=label,
                factor_b="conventional-baseline-v1",
                methodology="correlation+residualization+vif",
                parameters={"oos_only": True, "minimum_observations": 30},
                result={
                    "pearson": components["pearson_to_baseline"],
                    "spearman": components["spearman_to_baseline"],
                    "partial_correlation": components["partial_correlation"],
                    "vif_interpretation": "high" if kind == "redundant" else "low",
                    "pairwise_correlation_not_identity": True,
                },
                as_of_time=REFERENCE_INTELLIGENCE_AS_OF,
                checksum=_digest({"redundancy": label, "version": 1}),
            )
        )

    session.add_all(
        [
            FactorCluster(
                workspace_id=workspace_id,
                cluster_key="market-conventional",
                information_family="market",
                members=[{"factor": "conventional-overlap-factor", "similarity": 0.98}],
                methodology={"method": "correlation_distance", "causal_claim": False},
                version=1,
                as_of_time=REFERENCE_INTELLIGENCE_AS_OF,
            ),
            FactorCluster(
                workspace_id=workspace_id,
                cluster_key="external-driver-independent",
                information_family="energy",
                members=[{"factor": "external-driver-independent-factor", "similarity": 0.24}],
                methodology={"method": "correlation_distance", "causal_claim": False},
                version=1,
                as_of_time=REFERENCE_INTELLIGENCE_AS_OF,
            ),
        ]
    )

    definition = DivergenceDefinition(
        workspace_id=workspace_id,
        key="cross-domain-operating-pressure",
        name="Cross-domain operating pressure disagreement",
        domains=["fundamentals", "market", "external_driver"],
        required_features={
            "fundamentals": ["revenue_growth_yoy"],
            "market": ["momentum_90d"],
            "external_driver": ["fuel_cost_pressure"],
        },
        rules={
            "normalization": "point_in_time_rank",
            "minimum_coverage": 1.0,
            "minimum_disagreement_magnitude": 1.25,
            "lookback": 90,
            "minimum_persistence": 2,
            "confidence_threshold": 0.75,
        },
        temporal_truth_policy={
            "eligible_universe_only": True,
            "eligible_features_only": True,
            "future_cross_section_forbidden": True,
        },
        version=1,
    )
    session.add(definition)
    session.flush()
    event = detect_divergence(
        session,
        definition,
        subject_entity_id=airline_entity.id,
        as_of_time=REFERENCE_INTELLIGENCE_AS_OF,
        domain_values={"fundamentals": 0.72, "market": 0.61, "external_driver": -0.91},
        persistence_periods=3,
        historical_analogues=[
            {
                "memory_id": str(memories[1].id),
                "sample_size": 1,
                "warning": "tiny historical sample; no strength implied",
            }
        ],
    )
    if event is None:
        raise RuntimeError("reference divergence fixture did not meet its declarative definition")

    agriculture_memory = next(item for item in memories if item.conclusion == "NEGATIVE")
    agriculture_experiment, agriculture_hypothesis, _ = row_by_archetype["agriculture"]
    classify_hypothesis(
        session,
        agriculture_hypothesis,
        feature_key=agriculture_memory.feature_key,
        outcome_key=agriculture_memory.outcome_key,
        mechanism_checksum=agriculture_memory.mechanism_checksum,
    )
    classify_hypothesis(
        session,
        agriculture_hypothesis,
        feature_key=agriculture_memory.feature_key,
        outcome_key=agriculture_memory.outcome_key,
        mechanism_checksum=agriculture_memory.mechanism_checksum,
        override_authorized=True,
    )

    session.add(
        ResearchContradiction(
            workspace_id=workspace_id,
            memory_a_id=memories[0].id,
            memory_b_id=agriculture_memory.id,
            conflicting_dimension="business_model_applicability",
            context={
                "positive_context": "electricity-intensive manufacturing",
                "negative_context": "agricultural cooperative",
                "periods": ["reference OOS A", "reference OOS B"],
            },
            confidence=Decimal("0.800000"),
            possible_explanations=[
                "different business models",
                "different external-driver transmission paths",
            ],
            discovered_at=REFERENCE_INTELLIGENCE_AS_OF,
            simulation_eligible_time=REFERENCE_INTELLIGENCE_AS_OF,
        )
    )
    for resource_key, metrics, recommendation in (
        (
            "conventional_market_data",
            {
                "usage": 12,
                "redundant_contributions": 9,
                "independent_contributions": 1,
                "cpu_seconds": 18,
            },
            "Retain as a bounded baseline; avoid treating usage as unique information value.",
        ),
        (
            "energy_external_drivers",
            {
                "usage": 4,
                "redundant_contributions": 0,
                "independent_contributions": 3,
                "cpu_seconds": 11,
            },
            "Prioritize evidence-qualified research for energy-sensitive business models.",
        ),
    ):
        session.add(
            InformationValueRecord(
                workspace_id=workspace_id,
                resource_key=resource_key,
                resource_type="dataset_domain",
                metrics={
                    **metrics,
                    "hypotheses_supported": metrics["usage"],
                    "experiments_supported": metrics["usage"],
                    "rejected_experiments": 1,
                    "api_calls": 0,
                    "downloaded_bytes": 0,
                    "storage_bytes": 4096,
                    "maintenance_cost_class": "low",
                },
                recommendation=recommendation,
                sample_size=metrics["usage"],
                as_of_time=REFERENCE_INTELLIGENCE_AS_OF,
            )
        )
    for method, generated, duplicate, rejected in (
        ("graph-derived", 12, 1, 3),
        ("rule-derived", 8, 2, 4),
        ("manual", 3, 0, 1),
    ):
        session.add(
            ResearchMethodReliability(
                workspace_id=workspace_id,
                method=method,
                metrics={
                    "generated_count": generated,
                    "evidence_qualified_rate": 0.75,
                    "implementation_rate": 0.60,
                    "oos_survival": 0.35,
                    "robustness_survival": 0.30,
                    "multiple_testing_survival": 0.25,
                    "independent_information_contribution": 0.28,
                    "duplicate_rate": duplicate / generated,
                    "rejection_rate": rejected / generated,
                    "negative_control_failure_rate": 0.0,
                },
                sample_size=generated,
                interpretation=(
                    "Directional only; sample is too small to rank this origin as best."
                    if generated < 30
                    else "Sufficient sample for bounded comparison."
                ),
                as_of_time=REFERENCE_INTELLIGENCE_AS_OF,
            )
        )
    session.add_all(
        [
            ResearchOutcomeAttribution(
                workspace_id=workspace_id,
                experiment_id=agriculture_experiment.id,
                reason_code="no_oos_persistence",
                category="failure",
                passed=False,
                evidence={"source": "v0.10 promotion gate", "structured": True},
                simulation_eligible_time=agriculture_memory.simulation_eligible_time,
            ),
            ResearchOutcomeAttribution(
                workspace_id=workspace_id,
                experiment_id=airline_experiment.id,
                reason_code="useful_independent_contribution",
                category="success",
                passed=True,
                evidence={"source": "signal-independence-v1", "oos_only": True},
                simulation_eligible_time=REFERENCE_INTELLIGENCE_AS_OF,
            ),
        ]
    )
    session.flush()
    return _summary(session, workspace_id)


def _summary(session: Session, workspace_id: uuid.UUID) -> dict[str, Any]:
    from packages.database.models import (  # local import keeps fixture import list readable
        DivergenceEvent,
        HypothesisMemoryDecision,
        ResearchMemoryEntry,
    )

    memories = list(
        session.scalars(
            select(ResearchMemoryEntry).where(ResearchMemoryEntry.workspace_id == workspace_id)
        )
    )
    decisions = list(
        session.scalars(
            select(HypothesisMemoryDecision).where(
                HypothesisMemoryDecision.workspace_id == workspace_id
            )
        )
    )
    events = list(
        session.scalars(select(DivergenceEvent).where(DivergenceEvent.workspace_id == workspace_id))
    )
    return {
        "memory_count": len(memories),
        "negative_memory_count": sum(item.conclusion == "NEGATIVE" for item in memories),
        "known_failure_suppressed": any(item.decision == "SUPPRESSED" for item in decisions),
        "authorized_override_recorded": any(item.override_authorized for item in decisions),
        "divergence_count": len(events),
        "paper_eligible_from_divergence": False,
        "semantics": "research_intelligence_not_investment_recommendation",
    }
