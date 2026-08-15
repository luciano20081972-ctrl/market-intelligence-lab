from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from packages.core.time import utc_now
from packages.database.models import (
    FeedbackRecommendation,
    ForecastOutcomeObservation,
    ForecastScore,
    ForecastTargetDefinition,
    PaperAllocationCandidate,
    ResearchForecast,
    ResearchReliabilitySnapshot,
)
from packages.prospective_intelligence.service import (
    EvaluationMode,
    ForecastType,
    aggregate_scores,
    construct_portfolio,
    digest,
    rebalance_orders,
    research_risk,
    scenario_stress,
    score_forecast,
)

router = APIRouter(tags=["prospective-calibration-paper-portfolio"])


def _workspace_id(session: Session) -> uuid.UUID:
    value = session.info.get("workspace_id")
    if not isinstance(value, uuid.UUID):
        raise HTTPException(status_code=403, detail="Workspace context is required")
    return value


def _forecast(item: ResearchForecast) -> dict[str, Any]:
    now = utc_now()
    state = item.state
    if state == "LOCKED" and now >= item.outcome_eligible_time:
        state = "MATURED"
    return {
        "id": str(item.id),
        "target_definition_id": str(item.target_definition_id),
        "research_case_id": str(item.research_case_id) if item.research_case_id else None,
        "forecast_type": item.forecast_type,
        "forecast_value": item.forecast_value,
        "evaluation_mode": item.evaluation_mode,
        "state": state,
        "as_of_time": item.as_of_time,
        "target_start_time": item.target_start_time,
        "target_end_time": item.target_end_time,
        "outcome_eligible_time": item.outcome_eligible_time,
        "locked_at": item.locked_at,
        "manifest": item.manifest,
        "checksum": item.checksum,
        "immutable_when_locked": True,
    }


class ForecastCreate(BaseModel):
    target_key: str = Field(min_length=1, max_length=120)
    forecast_type: ForecastType
    forecast_value: dict[str, Any]
    evaluation_mode: EvaluationMode
    as_of_time: datetime
    target_start_time: datetime
    target_end_time: datetime
    outcome_eligible_time: datetime
    research_case_id: uuid.UUID | None = None
    manifest: dict[str, Any] = Field(default_factory=dict)


@router.get("/research/forecasts")
def list_forecasts(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = session.scalars(
        select(ResearchForecast)
        .where(ResearchForecast.workspace_id == _workspace_id(session))
        .order_by(ResearchForecast.as_of_time.desc())
    )
    return {
        "items": [_forecast(item) for item in items],
        "modes": [item.value for item in EvaluationMode],
        "semantics": "prospective_is_distinct_from_historical_replay_and_fixture",
    }


@router.post("/research/forecasts")
def post_forecast(body: ForecastCreate, session: Session = Depends(get_db)) -> dict[str, Any]:
    workspace = _workspace_id(session)
    if (
        body.target_start_time < body.as_of_time
        or body.outcome_eligible_time < body.target_end_time
    ):
        raise HTTPException(status_code=422, detail="Invalid point-in-time target boundary")
    target = session.scalar(
        select(ForecastTargetDefinition)
        .where(
            ForecastTargetDefinition.workspace_id == workspace,
            ForecastTargetDefinition.key == body.target_key,
        )
        .order_by(ForecastTargetDefinition.version.desc())
    )
    if target is None:
        target = ForecastTargetDefinition(
            workspace_id=workspace,
            key=body.target_key,
            version=1,
            outcome_type="VALIDATED_INTERMEDIATE_OUTCOME",
            specification={
                "source": "point-in-time",
                "transformation": "identity",
                "horizon": "explicit",
                "benchmark_policy": "frozen",
                "corporate_action_policy": "adjusted",
                "missing_data_policy": "invalidate",
                "timestamp_eligibility": "publication_time",
                "units": "declared",
            },
        )
        session.add(target)
        session.flush()
    manifest = {**body.manifest, "paper_only": True, "software_version": "0.13.0"}
    checksum = digest({**body.model_dump(), "workspace_id": workspace, "manifest": manifest})
    item = ResearchForecast(
        workspace_id=workspace,
        target_definition_id=target.id,
        research_case_id=body.research_case_id,
        forecast_type=body.forecast_type.value,
        forecast_value=body.forecast_value,
        evaluation_mode=body.evaluation_mode.value,
        state="OPEN",
        as_of_time=body.as_of_time,
        target_start_time=body.target_start_time,
        target_end_time=body.target_end_time,
        outcome_eligible_time=body.outcome_eligible_time,
        manifest=manifest,
        checksum=checksum,
    )
    session.add(item)
    session.commit()
    return _forecast(item)


@router.get("/research/forecasts/{forecast_id}")
def get_forecast(forecast_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    item = session.scalar(
        select(ResearchForecast).where(
            ResearchForecast.id == forecast_id,
            ResearchForecast.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Forecast was not found")
    return _forecast(item)


@router.post("/research/forecasts/{forecast_id}/lock")
def lock_forecast(forecast_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    item = session.scalar(
        select(ResearchForecast).where(
            ResearchForecast.id == forecast_id,
            ResearchForecast.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Forecast was not found")
    now = utc_now()
    if item.state != "OPEN" or now > item.outcome_eligible_time:
        raise HTTPException(status_code=409, detail="Forecast cannot be locked")
    item.state = "LOCKED"
    item.locked_at = now
    session.commit()
    return _forecast(item)


class OutcomeCreate(BaseModel):
    realized_value: dict[str, Any]
    observed_at: datetime
    source_manifest: dict[str, Any]


@router.post("/research/forecasts/{forecast_id}/observe")
def post_outcome(
    forecast_id: uuid.UUID, body: OutcomeCreate, session: Session = Depends(get_db)
) -> dict[str, Any]:
    item = session.scalar(
        select(ResearchForecast).where(
            ResearchForecast.id == forecast_id,
            ResearchForecast.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Forecast was not found")
    if item.locked_at is None or body.observed_at < item.outcome_eligible_time:
        raise HTTPException(status_code=409, detail="Outcome is not mature")
    previous = list(
        session.scalars(
            select(ForecastOutcomeObservation).where(
                ForecastOutcomeObservation.forecast_id == item.id
            )
        )
    )
    payload = {
        "forecast_id": str(item.id),
        "realized_value": body.realized_value,
        "observed_at": body.observed_at,
        "source_manifest": body.source_manifest,
        "version": len(previous) + 1,
    }
    observation = ForecastOutcomeObservation(
        workspace_id=item.workspace_id,
        forecast_id=item.id,
        version=len(previous) + 1,
        realized_value=body.realized_value,
        observed_at=body.observed_at,
        source_manifest=body.source_manifest,
        outcome_checksum=digest(payload),
    )
    session.add(observation)
    session.commit()
    return {
        **payload,
        "id": str(observation.id),
        "outcome_checksum": observation.outcome_checksum,
        "immutable": True,
    }


@router.get("/research/outcomes")
def list_outcomes(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = session.scalars(
        select(ForecastOutcomeObservation)
        .where(ForecastOutcomeObservation.workspace_id == _workspace_id(session))
        .order_by(ForecastOutcomeObservation.observed_at.desc())
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "forecast_id": str(item.forecast_id),
                "version": item.version,
                "realized_value": item.realized_value,
                "observed_at": item.observed_at,
                "outcome_checksum": item.outcome_checksum,
            }
            for item in items
        ]
    }


@router.get("/research/forecasts/{forecast_id}/score")
def get_score(forecast_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    forecast = session.scalar(
        select(ResearchForecast).where(
            ResearchForecast.id == forecast_id,
            ResearchForecast.workspace_id == _workspace_id(session),
        )
    )
    if forecast is None:
        raise HTTPException(status_code=404, detail="Forecast was not found")
    outcome = session.scalar(
        select(ForecastOutcomeObservation)
        .where(ForecastOutcomeObservation.forecast_id == forecast.id)
        .order_by(ForecastOutcomeObservation.version.desc())
    )
    if outcome is None:
        raise HTTPException(status_code=409, detail="No mature outcome is available")
    expected = forecast.forecast_value.get("value", forecast.forecast_value)
    realized = outcome.realized_value.get("value", outcome.realized_value)
    metrics = score_forecast(forecast.forecast_type, expected, realized)
    score = session.scalar(select(ForecastScore).where(ForecastScore.observation_id == outcome.id))
    if score is None:
        score = ForecastScore(
            workspace_id=forecast.workspace_id,
            forecast_id=forecast.id,
            observation_id=outcome.id,
            evaluation_mode=forecast.evaluation_mode,
            metrics=metrics,
            scored_at=utc_now(),
            checksum=digest([forecast.checksum, outcome.outcome_checksum, metrics]),
        )
        session.add(score)
        session.commit()
    return {
        "forecast_id": str(forecast.id),
        "forecast_type": forecast.forecast_type,
        "evaluation_mode": forecast.evaluation_mode,
        "metrics": score.metrics,
        "scored_at": score.scored_at,
    }


@router.get("/research/calibration")
def calibration(
    mode: EvaluationMode = EvaluationMode.PROSPECTIVE,
    as_of: datetime | None = None,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = session.execute(
        select(ForecastScore, ForecastOutcomeObservation)
        .join(
            ForecastOutcomeObservation,
            ForecastOutcomeObservation.id == ForecastScore.observation_id,
        )
        .where(
            ForecastScore.workspace_id == _workspace_id(session),
            ForecastScore.evaluation_mode == mode.value,
        )
    ).all()
    records = [
        {
            **score.metrics,
            "evaluation_mode": score.evaluation_mode,
            "observed_at": outcome.observed_at,
        }
        for score, outcome in rows
    ]
    return aggregate_scores(records, mode=mode, as_of=as_of)


@router.get("/research/calibration/confidence")
def confidence_calibration_view(session: Session = Depends(get_db)) -> dict[str, Any]:
    _workspace_id(session)
    return {
        "sample_count": 0,
        "status": "INSUFFICIENT_SAMPLE",
        "semantics": "research_confidence_is_not_probability",
    }


@router.get("/research/reliability")
def reliability(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = session.scalars(
        select(ResearchReliabilitySnapshot)
        .where(ResearchReliabilitySnapshot.workspace_id == _workspace_id(session))
        .order_by(ResearchReliabilitySnapshot.as_of_time.desc())
    )
    return {
        "items": [
            {
                "subject_type": item.subject_type,
                "subject_key": item.subject_key,
                "evaluation_mode": item.evaluation_mode,
                "sample_count": item.sample_count,
                "metrics": item.metrics,
                "as_of_time": item.as_of_time,
            }
            for item in items
        ]
    }


@router.get("/research/feedback")
def feedback(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = session.scalars(
        select(FeedbackRecommendation)
        .where(FeedbackRecommendation.workspace_id == _workspace_id(session))
        .order_by(FeedbackRecommendation.created_at.desc())
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "subject_type": item.subject_type,
                "subject_key": item.subject_key,
                "recommendation": item.recommendation,
                "status": item.status,
                "evidence": item.evidence,
            }
            for item in items
        ],
        "automatic_policy_changes": False,
    }


@router.get("/paper/allocation-candidates")
def candidates(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = session.scalars(
        select(PaperAllocationCandidate)
        .where(PaperAllocationCandidate.workspace_id == _workspace_id(session))
        .order_by(PaperAllocationCandidate.as_of_time.desc())
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "asset_symbol": item.asset_symbol,
                "direction": item.direction,
                "calibration_state": item.calibration_state,
                "priority": item.priority,
                "evidence": item.evidence,
                "paper_only": True,
            }
            for item in items
        ],
        "label": "SIMULATED / PAPER ONLY",
    }


class PlanCreate(BaseModel):
    scores: dict[str, float]
    domains: dict[str, str]
    current_weights: dict[str, float] = Field(default_factory=dict)
    prices: dict[str, float]
    equity: float = Field(gt=0)
    method: str = "SCORE_CAPPED"
    max_position: float = Field(default=0.2, gt=0, le=1)
    min_cash: float = Field(default=0.1, ge=0, le=1)
    max_domain: float = Field(default=0.4, gt=0, le=1)
    scenario_shocks: dict[str, dict[str, float]] = Field(default_factory=dict)
    execution_mode: str = "MANUAL_PREVIEW"


@router.post("/paper/plans")
def create_plan(body: PlanCreate, session: Session = Depends(get_db)) -> dict[str, Any]:
    _workspace_id(session)
    if body.execution_mode not in {"MANUAL_PREVIEW", "AUTO_SIMULATED"}:
        raise HTTPException(status_code=422, detail="Unsupported paper execution mode")
    portfolio = construct_portfolio(
        body.scores, method=body.method, max_position=body.max_position, min_cash=body.min_cash
    )
    risk = research_risk(
        portfolio["weights"],
        body.domains,
        max_position=body.max_position,
        max_domain=body.max_domain,
    )
    stress = scenario_stress(portfolio["weights"], body.scenario_shocks)
    approved = risk["approved"] and stress["approved"]
    plan_id = digest(body.model_dump())[:32]
    orders = (
        rebalance_orders(
            body.current_weights, portfolio["weights"], body.equity, body.prices, plan_id
        )
        if approved
        else []
    )
    return {
        "id": plan_id,
        "status": "APPROVED_FOR_SIMULATION" if approved else "REJECTED",
        "target_weights": portfolio["weights"],
        "cash_weight": portfolio["cash_weight"],
        "risk_review": risk,
        "scenario_stress": stress,
        "order_preview": orders,
        "execution_mode": body.execution_mode,
        "label": "SIMULATED / PAPER ONLY",
        "brokerage_connectivity": False,
    }


@router.get("/paper/plans")
def list_plans(session: Session = Depends(get_db)) -> dict[str, Any]:
    _workspace_id(session)
    return {"items": [], "label": "SIMULATED / PAPER ONLY"}


@router.get("/paper/evaluation")
def evaluation(session: Session = Depends(get_db)) -> dict[str, Any]:
    _workspace_id(session)
    return {"items": [], "label": "SIMULATED / PAPER ONLY", "forecast_quality_separate": True}


@router.get("/paper/attribution")
def attribution(session: Session = Depends(get_db)) -> dict[str, Any]:
    _workspace_id(session)
    return {"items": [], "causality_claimed": False, "label": "SIMULATED / PAPER ONLY"}
