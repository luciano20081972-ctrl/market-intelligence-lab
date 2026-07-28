from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from apps.api.dependencies import get_db
from apps.api.schemas_sprint2 import (
    StrategyCreate,
    StrategyPage,
    StrategyResponse,
    StrategyVersionCreate,
    StrategyVersionResponse,
)
from packages.database.models import Strategy, StrategyVersion
from packages.provenance import record_audit_event
from packages.strategies.registry import get_strategy_definition, validate_strategy_parameters

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _find_strategy(session: Session, strategy_id: UUID) -> Strategy:
    strategy = session.scalar(
        select(Strategy)
        .where(Strategy.id == strategy_id)
        .options(selectinload(Strategy.versions))
        .execution_options(populate_existing=True)
    )
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy was not found")
    return strategy


def _version_response(version: StrategyVersion) -> StrategyVersionResponse:
    return StrategyVersionResponse(
        id=version.id,
        version=version.version,
        parameters=version.parameters,
        parameter_schema=version.parameter_schema,
        calculation_notes=version.calculation_notes,
        created_at=version.created_at,
    )


def _strategy_response(strategy: Strategy, include_versions: bool = False) -> StrategyResponse:
    versions = sorted(strategy.versions, key=lambda value: value.version)
    if not versions:
        raise RuntimeError("strategy has no version")
    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        strategy_type=strategy.strategy_type,
        description=strategy.description,
        is_builtin=strategy.is_builtin,
        latest_version=_version_response(versions[-1]),
        versions=[_version_response(version) for version in versions] if include_versions else [],
    )


@router.get("", response_model=StrategyPage)
def list_strategies(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> StrategyPage:
    total = session.scalar(select(func.count(Strategy.id))) or 0
    strategies = session.scalars(
        select(Strategy)
        .options(selectinload(Strategy.versions))
        .order_by(Strategy.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return StrategyPage(
        items=[_strategy_response(strategy) for strategy in strategies],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
def create_strategy(
    payload: StrategyCreate, session: Session = Depends(get_db)
) -> StrategyResponse:
    try:
        definition = get_strategy_definition(payload.strategy_type)
        parameters = validate_strategy_parameters(payload.strategy_type, payload.parameters)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    strategy = Strategy(
        name=payload.name,
        strategy_type=payload.strategy_type,
        description=payload.description or definition.description,
        is_builtin=False,
    )
    try:
        session.add(strategy)
        session.flush()
        session.add(
            StrategyVersion(
                strategy_id=strategy.id,
                version=1,
                parameters=parameters,
                parameter_schema=definition.parameters_model.model_json_schema(),
                calculation_notes=definition.calculation_notes,
            )
        )
        record_audit_event(
            session,
            action="strategy.created",
            entity_type="strategy",
            entity_id=strategy.id,
            details={"strategy_type": strategy.strategy_type},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A strategy with that name already exists"
        ) from exc
    return _strategy_response(_find_strategy(session, strategy.id), include_versions=True)


@router.get("/{strategy_id}", response_model=StrategyResponse)
def get_strategy(strategy_id: UUID, session: Session = Depends(get_db)) -> StrategyResponse:
    return _strategy_response(_find_strategy(session, strategy_id), include_versions=True)


@router.post(
    "/{strategy_id}/versions",
    response_model=StrategyVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_strategy_version(
    strategy_id: UUID,
    payload: StrategyVersionCreate,
    session: Session = Depends(get_db),
) -> StrategyVersionResponse:
    strategy = _find_strategy(session, strategy_id)
    try:
        parameters = validate_strategy_parameters(strategy.strategy_type, payload.parameters)
        definition = get_strategy_definition(strategy.strategy_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    next_version = max(version.version for version in strategy.versions) + 1
    version = StrategyVersion(
        strategy_id=strategy.id,
        version=next_version,
        parameters=parameters,
        parameter_schema=definition.parameters_model.model_json_schema(),
        calculation_notes=definition.calculation_notes,
    )
    session.add(version)
    record_audit_event(
        session,
        action="strategy.version_created",
        entity_type="strategy",
        entity_id=strategy.id,
        details={"version": next_version},
    )
    session.commit()
    session.refresh(version)
    return _version_response(version)
