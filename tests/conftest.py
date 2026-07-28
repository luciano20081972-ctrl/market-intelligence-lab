from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from apps.api.main import create_app
from packages.core.config import Settings
from packages.database.base import Base
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.market_data.seed import seed_demonstration_data


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    value = create_database_engine(database_url)
    Base.metadata.create_all(value)
    factory = make_session_factory(value)
    with session_scope(factory) as session:
        seed_demonstration_data(session)
    yield value
    value.dispose()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    settings = Settings(database_url="sqlite:///:memory:", environment="test")
    with TestClient(create_app(settings=settings, engine=engine)) as value:
        yield value
