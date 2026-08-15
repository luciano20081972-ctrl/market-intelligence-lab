from __future__ import annotations

import hashlib
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db, get_workspace_context
from packages.database.models import OptimizationExperiment
from packages.optimization import SkfolioOptimizerAdapter
from packages.security import WorkspaceContext

router = APIRouter(prefix="/optimization", tags=["portfolio optimization"])


class OptimizationRequest(BaseModel):
    model: str = "minimum_variance"
    asset_returns: dict[str, list[float]]
    training_start: date
    training_end: date
    validation_start: date
    validation_end: date
    allow_short: bool = False
    allow_leverage: bool = False
    random_seed: int = Field(default=0, ge=0, le=2**31 - 1)


@router.post("/experiments", status_code=status.HTTP_201_CREATED)
def create_experiment(
    payload: OptimizationRequest,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    if not (
        payload.training_start
        < payload.training_end
        < payload.validation_start
        < payload.validation_end
    ):
        raise HTTPException(
            status_code=422, detail="Training and validation periods must not overlap"
        )
    adapter = SkfolioOptimizerAdapter()
    returns = {symbol.upper(): tuple(values) for symbol, values in payload.asset_returns.items()}
    try:
        result = adapter.optimize(
            returns,
            model=payload.model,
            allow_short=payload.allow_short,
            allow_leverage=payload.allow_leverage,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    checksum = hashlib.sha256(
        json.dumps(payload.asset_returns, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    experiment = OptimizationExperiment(
        workspace_id=context.workspace_id,
        model=payload.model,
        hyperparameters={"random_seed": payload.random_seed},
        asset_universe=sorted(returns),
        input_return_checksum=checksum,
        covariance_estimator={"name": "empirical"},
        expected_return_estimator={"name": "historical_mean"},
        constraints={"allow_short": False, "allow_leverage": False, "weight_bounds": [0, 1]},
        training_period={
            "start": payload.training_start.isoformat(),
            "end": payload.training_end.isoformat(),
        },
        validation_period={
            "start": payload.validation_start.isoformat(),
            "end": payload.validation_end.isoformat(),
        },
        resulting_weights=result["weights"],
        objective_values=result["objective_values"],
        risk_metrics=result["risk_metrics"],
        optimizer_version=str(result["optimizer_version"]),
        random_seed=payload.random_seed,
        warnings=result["warnings"],
        failure_reason=None,
    )
    session.add(experiment)
    session.commit()
    return {
        "id": experiment.id,
        "model": experiment.model,
        "asset_universe": experiment.asset_universe,
        "weights": experiment.resulting_weights,
        "objective_values": experiment.objective_values,
        "risk_metrics": experiment.risk_metrics,
        "constraints": experiment.constraints,
        "optimizer_version": experiment.optimizer_version,
        "warnings": experiment.warnings,
        "input_return_checksum": checksum,
    }
