from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.adversarial_intelligence.service import (
    confidence_profile,
    digest,
    generate_challenges,
    review_status,
)
from packages.database.models import (
    CounterfactualDefinition,
    EconomicEntity,
    FactorExperiment,
    ResearchAssumption,
    ResearchCase,
    ResearchConfidenceProfile,
    ResearchDossier,
    ResearchFragilityAnalysis,
    ResearchHypothesis,
    ScenarioDefinition,
    SkepticChallenge,
    SkepticReview,
)

REFERENCE_AS_OF = datetime(2026, 8, 15, 12, tzinfo=UTC)


def seed_reference_adversarial_intelligence(
    session: Session, workspace_id: uuid.UUID
) -> dict[str, Any]:
    existing = session.scalar(select(ResearchCase).where(ResearchCase.workspace_id == workspace_id))
    if existing is not None:
        return _summary(session, workspace_id)
    entities = list(
        session.scalars(
            select(EconomicEntity)
            .where(EconomicEntity.workspace_id == workspace_id)
            .order_by(EconomicEntity.canonical_name)
        )
    )
    hypotheses = list(
        session.scalars(
            select(ResearchHypothesis)
            .where(ResearchHypothesis.workspace_id == workspace_id)
            .order_by(ResearchHypothesis.created_at)
        )
    )
    experiments = list(
        session.scalars(
            select(FactorExperiment)
            .where(FactorExperiment.workspace_id == workspace_id)
            .order_by(FactorExperiment.created_at)
        )
    )
    if len(entities) < 3 or len(hypotheses) < 3 or len(experiments) < 3:
        raise ValueError("seed v0.10 and v0.11 reference research before v0.12 fixtures")

    archetypes = (
        (
            "Semiconductor energy and packaging stress",
            entities[0],
            hypotheses[0],
            experiments[0],
            {"entity_ambiguous": True, "missing_mechanism": True},
            "BLOCKED",
            "FRAGILE",
        ),
        (
            "Airline fuel, weather, and congestion stress",
            entities[1],
            hypotheses[1],
            experiments[1],
            {"high_redundancy": True, "single_regime": True},
            "NEEDS_EVIDENCE",
            "MODERATELY_SENSITIVE",
        ),
        (
            "Agriculture drought, fertilizer, and water stress",
            entities[2],
            hypotheses[2],
            experiments[2],
            {"memory_contradiction": True, "low_coverage": True},
            "NEEDS_EVIDENCE",
            "MODERATELY_SENSITIVE",
        ),
    )
    for index, (
        title,
        entity,
        hypothesis,
        experiment,
        signals,
        expected_status,
        fragility,
    ) in enumerate(archetypes):
        case_checksum = digest(
            {"workspace": workspace_id, "title": title, "as_of": REFERENCE_AS_OF}
        )
        case = ResearchCase(
            workspace_id=workspace_id,
            subject_entity_id=entity.id,
            hypothesis_id=hypothesis.id,
            experiment_id=experiment.id,
            title=title,
            references={
                "graph_paths": hypothesis.machine_readable_mechanism,
                "memory_query_as_of": REFERENCE_AS_OF.isoformat(),
                "feature_snapshot": str(experiment.feature_snapshot_id),
                "source_manifests": [experiment.checksum],
            },
            promotion_state="REVIEW_REQUIRED",
            as_of_time=REFERENCE_AS_OF,
            simulation_eligible_time=REFERENCE_AS_OF,
            checksum=case_checksum,
        )
        session.add(case)
        session.flush()
        generated = generate_challenges({**signals, "claim": title})
        status = review_status(generated)
        assert status == expected_status
        manifest = {
            "software_sha": "fixture-v0.12",
            "alembic_revision": "e2517ff0412b",
            "research_case_checksum": case_checksum,
            "hypothesis_checksum": hypothesis.checksum,
            "experiment_checksum": experiment.checksum,
            "graph_state": "point-in-time",
            "memory_as_of": REFERENCE_AS_OF.isoformat(),
            "as_of_time": REFERENCE_AS_OF.isoformat(),
            "policy": "skeptic-policy-v1",
            "seed": 0,
        }
        review = SkepticReview(
            workspace_id=workspace_id,
            research_case_id=case.id,
            status=status,
            policy_version="skeptic-policy-v1",
            manifest=manifest,
            as_of_time=REFERENCE_AS_OF,
            simulation_eligible_time=REFERENCE_AS_OF,
            checksum=digest(manifest),
            completed_at=REFERENCE_AS_OF,
        )
        session.add(review)
        session.flush()
        for challenge in generated:
            session.add(
                SkepticChallenge(
                    workspace_id=workspace_id,
                    review_id=review.id,
                    category=challenge["category"],
                    severity=challenge["severity"],
                    title=challenge["title"],
                    challenge=challenge["challenge"],
                    evidence={
                        "supporting": challenge["supporting_evidence"],
                        "contradicting": challenge["contradicting_evidence"],
                    },
                    affected_claim=challenge["affected_claim"],
                    falsification_condition=challenge["falsification_condition"],
                    proposed_test=challenge["proposed_test"],
                    resolution={},
                    status="OPEN",
                    confidence=Decimal("1.0"),
                    simulation_eligible_time=REFERENCE_AS_OF,
                )
            )
        session.add(
            ResearchAssumption(
                workspace_id=workspace_id,
                research_case_id=case.id,
                assumption_type="MECHANISM",
                statement=(
                    "Transmission applies only through evidence-supported graph relationships."
                ),
                evidence={"graph_state": "point-in-time"},
                importance="CRITICAL",
                sensitivity="TESTED",
                status="CHALLENGED",
            )
        )
        profile = confidence_profile(
            {
                "evidence_quality": 0.7,
                "source_reliability": 0.8,
                "data_coverage": 0.5,
                "temporal_safety": 1.0,
                "mechanism_support": 0.6,
                "oos_robustness": 0.7,
                "multiple_testing_survival": 0.8,
                "independent_information": 0.5,
                "regime_stability": 0.4,
                "memory_consistency": 0.4 if index == 2 else 0.7,
                "skeptic_risk": 0.2,
                "scenario_robustness": 0.5,
                "counterfactual_robustness": 0.5,
            }
        )
        confidence_manifest = {**manifest, "formula": profile["formula_version"]}
        session.add(
            ResearchConfidenceProfile(
                workspace_id=workspace_id,
                research_case_id=case.id,
                formula_version=profile["formula_version"],
                components=profile["components"],
                classification=profile["classification"],
                manifest=confidence_manifest,
                as_of_time=REFERENCE_AS_OF,
                checksum=digest(confidence_manifest),
            )
        )
        session.add(
            ResearchFragilityAnalysis(
                workspace_id=workspace_id,
                research_case_id=case.id,
                classification=fragility,
                components={
                    "alternate_lags": True,
                    "alternate_regimes": True,
                    "driver_removal": True,
                    "interpretation": "sensitivity_not_probability",
                },
                as_of_time=REFERENCE_AS_OF,
            )
        )
        scenario_payload = {"title": title, "index": index, "as_of": REFERENCE_AS_OF}
        scenario = ScenarioDefinition(
            workspace_id=workspace_id,
            title=title,
            description="Deterministic reference stress with all sensitivity points retained.",
            scenario_type="STRESS",
            plausibility="MEDIUM",
            horizon="one year",
            assumptions=[
                {
                    "shocks": [{"target": "external_driver", "value": 0.2 + index * 0.05}],
                    "edges": [
                        {
                            "source": "external_driver",
                            "target": str(entity.id),
                            "relationship": "evidence-supported exposure",
                            "supported": True,
                            "confidence": 0.8,
                            "weight": 0.5,
                            "function": "WEIGHTED_EXPOSURE",
                            "lag": 1,
                        }
                    ],
                }
            ],
            source_evidence=[{"research_case_id": str(case.id)}],
            as_of_time=REFERENCE_AS_OF,
            version=1,
            checksum=digest(scenario_payload),
        )
        session.add(scenario)
        counterfactual = CounterfactualDefinition(
            workspace_id=workspace_id,
            title=f"Remove primary driver: {title}",
            reference_state={
                "drivers": {"external_driver": 0.2},
                "canonical_evidence_checksum": case_checksum,
            },
            intervention={"operation": "REMOVE_DRIVER", "target": "external_driver"},
            mechanism_path=[{"research_case_id": str(case.id)}],
            assumptions=[{"isolated_simulation": True}],
            identification_status="SIMULATED_MECHANISM",
            as_of_time=REFERENCE_AS_OF,
            horizon="one year",
            version=1,
        )
        session.add(counterfactual)
        dossier_manifest = {
            **manifest,
            "scenario_checksum": scenario.checksum,
            "counterfactual_identification": "SIMULATED_MECHANISM",
        }
        session.add(
            ResearchDossier(
                workspace_id=workspace_id,
                research_case_id=case.id,
                title=title,
                sections={
                    "entity": entity.canonical_name,
                    "graph_paths": hypothesis.machine_readable_mechanism,
                    "hypothesis": str(hypothesis.id),
                    "experiment": str(experiment.id),
                    "contradictions": signals,
                    "skeptic_challenges": generated,
                    "critical_assumptions": ["supported graph transmission"],
                    "falsification_conditions": [
                        item["falsification_condition"] for item in generated
                    ],
                    "next_evidence": [item["proposed_test"] for item in generated],
                    "recommendation": None,
                },
                manifest=dossier_manifest,
                as_of_time=REFERENCE_AS_OF,
                checksum=digest(dossier_manifest),
            )
        )
    session.flush()
    return _summary(session, workspace_id)


def _summary(session: Session, workspace_id: uuid.UUID) -> dict[str, Any]:
    reviews = list(
        session.scalars(select(SkepticReview).where(SkepticReview.workspace_id == workspace_id))
    )
    return {
        "research_case_count": session.query(ResearchCase)
        .filter_by(workspace_id=workspace_id)
        .count(),
        "review_count": len(reviews),
        "blocked_count": sum(item.status == "BLOCKED" for item in reviews),
        "scenario_count": session.query(ScenarioDefinition)
        .filter_by(workspace_id=workspace_id)
        .count(),
        "counterfactual_count": session.query(CounterfactualDefinition)
        .filter_by(workspace_id=workspace_id)
        .count(),
        "no_trade_recommendations": True,
    }
