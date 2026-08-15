from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from packages.adversarial_intelligence.service import (
    digest,
    propagate_scenario,
    review_status,
    run_counterfactual,
)
from packages.core.time import utc_now
from packages.database.models import (
    CounterfactualDefinition,
    CounterfactualRun,
    ResearchConfidenceProfile,
    ResearchDossier,
    ScenarioDefinition,
    ScenarioRun,
    SkepticChallenge,
    SkepticReview,
)

router = APIRouter(tags=["adversarial-research"])


def _workspace_id(session: Session) -> uuid.UUID:
    value = session.info.get("workspace_id")
    if not isinstance(value, uuid.UUID):
        raise HTTPException(status_code=403, detail="Workspace context is required")
    return value


@router.post("/research/adversarial/reference-fixture")
def create_reference_fixture(session: Session = Depends(get_db)) -> dict[str, Any]:
    from packages.adversarial_intelligence.fixtures import seed_reference_adversarial_intelligence

    try:
        result = seed_reference_adversarial_intelligence(session, _workspace_id(session))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    session.commit()
    return result


class ScenarioCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str
    scenario_type: str = "CUSTOM"
    plausibility: str = "MEDIUM"
    horizon: str = "one year"
    as_of_time: datetime
    shocks: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class CounterfactualCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    reference_state: dict[str, Any]
    intervention: dict[str, Any]
    mechanism_path: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    as_of_time: datetime
    horizon: str = "one year"


def _challenge(item: SkepticChallenge) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "review_id": str(item.review_id),
        "category": item.category,
        "severity": item.severity,
        "title": item.title,
        "challenge": item.challenge,
        "evidence": item.evidence,
        "affected_claim": item.affected_claim,
        "falsification_condition": item.falsification_condition,
        "proposed_test": item.proposed_test,
        "resolution": item.resolution,
        "status": item.status,
        "confidence": str(item.confidence),
        "simulation_eligible_time": item.simulation_eligible_time,
    }


@router.get("/research/skeptic/reviews")
def list_reviews(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = list(
        session.scalars(
            select(SkepticReview)
            .where(SkepticReview.workspace_id == _workspace_id(session))
            .order_by(SkepticReview.as_of_time.desc())
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "research_case_id": str(item.research_case_id),
                "status": item.status,
                "policy_version": item.policy_version,
                "manifest": item.manifest,
                "as_of_time": item.as_of_time,
            }
            for item in items
        ]
    }


@router.get("/research/skeptic/reviews/{review_id}")
def review_detail(review_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    item = session.scalar(
        select(SkepticReview).where(
            SkepticReview.id == review_id, SkepticReview.workspace_id == _workspace_id(session)
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Skeptic review was not found")
    challenges = list(
        session.scalars(select(SkepticChallenge).where(SkepticChallenge.review_id == item.id))
    )
    return {
        "id": str(item.id),
        "status": item.status,
        "manifest": item.manifest,
        "challenges": [_challenge(challenge) for challenge in challenges],
        "semantics": "adversarial_review_does_not_establish_truth",
    }


@router.get("/research/skeptic/challenges")
def list_challenges(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = list(
        session.scalars(
            select(SkepticChallenge)
            .where(SkepticChallenge.workspace_id == _workspace_id(session))
            .order_by(SkepticChallenge.severity, SkepticChallenge.created_at)
        )
    )
    return {"items": [_challenge(item) for item in items]}


class ChallengeResolution(BaseModel):
    test_id: str
    result_checksum: str = Field(min_length=64, max_length=64)
    evidence: dict[str, Any] = Field(default_factory=dict)


@router.post("/research/skeptic/reviews/{review_id}/resolve")
def resolve_review(
    review_id: uuid.UUID, body: ChallengeResolution, session: Session = Depends(get_db)
) -> dict[str, Any]:
    review = session.scalar(
        select(SkepticReview).where(
            SkepticReview.id == review_id, SkepticReview.workspace_id == _workspace_id(session)
        )
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Skeptic review was not found")
    challenge = session.scalar(
        select(SkepticChallenge).where(
            SkepticChallenge.review_id == review.id, SkepticChallenge.status == "TESTING"
        )
    )
    if challenge is None:
        raise HTTPException(status_code=409, detail="No challenge is awaiting this test result")
    previous = list(
        session.scalars(select(SkepticChallenge).where(SkepticChallenge.review_id == review.id))
    )
    states = [
        {
            "severity": item.severity,
            "status": "RESOLVED" if item.id == challenge.id else item.status,
        }
        for item in previous
    ]
    now = utc_now()
    resolution = body.model_dump()
    manifest = {
        **review.manifest,
        "parent_review_checksum": review.checksum,
        "resolution": resolution,
        "as_of_time": now.isoformat(),
    }
    replacement = SkepticReview(
        workspace_id=review.workspace_id,
        research_case_id=review.research_case_id,
        status=review_status(states),
        policy_version=review.policy_version,
        manifest=manifest,
        as_of_time=now,
        simulation_eligible_time=now,
        checksum=digest(manifest),
        completed_at=now,
    )
    session.add(replacement)
    session.flush()
    for item in previous:
        resolved = item.id == challenge.id
        session.add(
            SkepticChallenge(
                workspace_id=item.workspace_id,
                review_id=replacement.id,
                category=item.category,
                severity=item.severity,
                title=item.title,
                challenge=item.challenge,
                evidence=item.evidence,
                affected_claim=item.affected_claim,
                falsification_condition=item.falsification_condition,
                proposed_test=item.proposed_test,
                resolution=resolution if resolved else item.resolution,
                status="RESOLVED" if resolved else item.status,
                confidence=item.confidence,
                simulation_eligible_time=now,
            )
        )
    session.commit()
    return {
        "review_id": str(replacement.id),
        "supersedes_review_id": str(review.id),
        "status": replacement.status,
        "resolved_challenge_id": str(challenge.id),
    }


@router.get("/research/scenarios")
def list_scenarios(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = list(
        session.scalars(
            select(ScenarioDefinition).where(
                ScenarioDefinition.workspace_id == _workspace_id(session)
            )
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "title": item.title,
                "description": item.description,
                "scenario_type": item.scenario_type,
                "plausibility": item.plausibility,
                "horizon": item.horizon,
                "as_of_time": item.as_of_time,
                "version": item.version,
                "semantics": "scenario_not_forecast",
            }
            for item in items
        ]
    }


@router.post("/research/scenarios")
def create_scenario(body: ScenarioCreate, session: Session = Depends(get_db)) -> dict[str, Any]:
    from packages.adversarial_intelligence.service import digest

    payload = body.model_dump(mode="json")
    item = ScenarioDefinition(
        workspace_id=_workspace_id(session),
        title=body.title,
        description=body.description,
        scenario_type=body.scenario_type,
        plausibility=body.plausibility,
        horizon=body.horizon,
        assumptions=[{"shocks": body.shocks, "edges": body.edges}],
        source_evidence=[],
        as_of_time=body.as_of_time,
        version=1,
        checksum=digest(payload),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"id": str(item.id), "checksum": item.checksum}


@router.get("/research/scenarios/{scenario_id}")
def scenario_detail(scenario_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    item = session.scalar(
        select(ScenarioDefinition).where(
            ScenarioDefinition.id == scenario_id,
            ScenarioDefinition.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Scenario was not found")
    runs = list(session.scalars(select(ScenarioRun).where(ScenarioRun.scenario_id == item.id)))
    return {
        "id": str(item.id),
        "title": item.title,
        "description": item.description,
        "plausibility": item.plausibility,
        "assumptions": item.assumptions,
        "runs": [
            {"id": str(run.id), "results": run.results, "manifest": run.manifest} for run in runs
        ],
        "warning": "THIS IS A SCENARIO, NOT A FORECAST",
    }


@router.post("/research/scenarios/{scenario_id}/run")
def run_scenario(scenario_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    from packages.adversarial_intelligence.service import digest

    item = session.scalar(
        select(ScenarioDefinition).where(
            ScenarioDefinition.id == scenario_id,
            ScenarioDefinition.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Scenario was not found")
    configuration = item.assumptions[0] if item.assumptions else {}
    impacts = propagate_scenario(configuration.get("shocks", []), configuration.get("edges", []))
    manifest = {
        "software_sha": "runtime",
        "alembic_revision": "v0.12",
        "scenario_checksum": item.checksum,
        "as_of_time": item.as_of_time.isoformat(),
        "seed": 0,
        "bounded_depth": 4,
    }
    checksum = digest({"manifest": manifest, "impacts": impacts})
    run = ScenarioRun(
        workspace_id=item.workspace_id,
        scenario_id=item.id,
        status="COMPLETED",
        manifest=manifest,
        results={"impacts": impacts, "no_trade_recommendation": True},
        as_of_time=item.as_of_time,
        checksum=checksum,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return {
        "id": str(run.id),
        "impacts": impacts,
        "checksum": checksum,
        "warning": "THIS IS A SCENARIO, NOT A FORECAST",
    }


@router.get("/research/counterfactuals")
def list_counterfactuals(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = list(
        session.scalars(
            select(CounterfactualDefinition).where(
                CounterfactualDefinition.workspace_id == _workspace_id(session)
            )
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "title": item.title,
                "identification_status": item.identification_status,
                "as_of_time": item.as_of_time,
            }
            for item in items
        ]
    }


@router.post("/research/counterfactuals")
def create_counterfactual(
    body: CounterfactualCreate, session: Session = Depends(get_db)
) -> dict[str, Any]:
    item = CounterfactualDefinition(
        workspace_id=_workspace_id(session),
        title=body.title,
        reference_state=body.reference_state,
        intervention=body.intervention,
        mechanism_path=body.mechanism_path,
        assumptions=body.assumptions,
        identification_status="SIMULATED_MECHANISM",
        as_of_time=body.as_of_time,
        horizon=body.horizon,
        version=1,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"id": str(item.id), "identification_status": item.identification_status}


@router.get("/research/counterfactuals/{definition_id}")
def counterfactual_detail(
    definition_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, Any]:
    item = session.scalar(
        select(CounterfactualDefinition).where(
            CounterfactualDefinition.id == definition_id,
            CounterfactualDefinition.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Counterfactual was not found")
    return {
        "id": str(item.id),
        "title": item.title,
        "reference_state": item.reference_state,
        "intervention": item.intervention,
        "identification_status": item.identification_status,
        "warning": "THIS IS A SIMULATED ALTERNATIVE STATE, NOT PROVEN CAUSAL EFFECT",
    }


@router.post("/research/counterfactuals/{definition_id}/run")
def execute_counterfactual(
    definition_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, Any]:
    item = session.scalar(
        select(CounterfactualDefinition).where(
            CounterfactualDefinition.id == definition_id,
            CounterfactualDefinition.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Counterfactual was not found")
    result = run_counterfactual(item.reference_state, item.intervention)
    run = CounterfactualRun(
        workspace_id=item.workspace_id,
        definition_id=item.id,
        status="COMPLETED",
        manifest={
            "definition_version": item.version,
            "as_of_time": item.as_of_time.isoformat(),
            "canonical_state_unchanged": True,
        },
        comparison=result,
        identification_status="SIMULATED_MECHANISM",
        as_of_time=item.as_of_time,
        checksum=result["checksum"],
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return {"id": str(run.id), **result}


@router.get("/research/confidence")
def list_confidence(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = list(
        session.scalars(
            select(ResearchConfidenceProfile).where(
                ResearchConfidenceProfile.workspace_id == _workspace_id(session)
            )
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "research_case_id": str(item.research_case_id),
                "formula_version": item.formula_version,
                "components": item.components,
                "classification": item.classification,
                "semantics": "not_a_probability",
            }
            for item in items
        ]
    }


@router.get("/research/dossiers")
def list_dossiers(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = list(
        session.scalars(
            select(ResearchDossier).where(ResearchDossier.workspace_id == _workspace_id(session))
        )
    )
    return {
        "items": [
            {"id": str(item.id), "title": item.title, "as_of_time": item.as_of_time}
            for item in items
        ]
    }


@router.get("/research/dossiers/{dossier_id}")
def dossier_detail(dossier_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    item = session.scalar(
        select(ResearchDossier).where(
            ResearchDossier.id == dossier_id, ResearchDossier.workspace_id == _workspace_id(session)
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Research dossier was not found")
    return {
        "id": str(item.id),
        "title": item.title,
        "sections": item.sections,
        "manifest": item.manifest,
        "no_investment_recommendation": True,
    }
