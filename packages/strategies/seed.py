from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from packages.database.models import Strategy, StrategyVersion
from packages.strategies.registry import STRATEGY_DEFINITIONS, default_strategy_parameters

STRATEGY_NAMESPACE = uuid.UUID("c61d0675-aeee-4ff2-96c3-288ead0227b1")


def seed_builtin_strategies(session: Session) -> int:
    inserted = 0
    for definition in STRATEGY_DEFINITIONS.values():
        strategy_id = uuid.uuid5(STRATEGY_NAMESPACE, f"strategy:{definition.key}")
        strategy = session.get(Strategy, strategy_id)
        if strategy is None:
            strategy = Strategy(
                id=strategy_id,
                name=definition.name,
                strategy_type=definition.key,
                description=definition.description,
                is_builtin=True,
            )
            session.add(strategy)
            session.flush()
            inserted += 1
        version_id = uuid.uuid5(STRATEGY_NAMESPACE, f"strategy:{definition.key}:v1")
        if session.get(StrategyVersion, version_id) is None:
            session.add(
                StrategyVersion(
                    id=version_id,
                    strategy_id=strategy.id,
                    version=1,
                    parameters=default_strategy_parameters(definition.key),
                    parameter_schema=definition.parameters_model.model_json_schema(),
                    calculation_notes=definition.calculation_notes,
                )
            )
    session.flush()
    return inserted
