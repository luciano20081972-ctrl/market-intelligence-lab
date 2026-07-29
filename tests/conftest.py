import shutil
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from apps.api.main import create_app
from packages.core.config import Settings
from packages.database.base import Base
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.market_data.seed import seed_demonstration_data


@pytest.fixture(scope="session")
def seeded_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    database_path = tmp_path_factory.mktemp("seeded-database") / "template.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    value = create_database_engine(database_url)
    Base.metadata.create_all(value)
    factory = make_session_factory(value)
    with session_scope(factory) as session:
        seed_demonstration_data(
            session,
            calendar_start=date(2025, 1, 1),
            calendar_end=date(2027, 12, 31),
        )
    value.dispose()
    return database_path


@pytest.fixture
def engine(tmp_path: Path, seeded_database: Path) -> Iterator[Engine]:
    database_path = tmp_path / "test.db"
    shutil.copyfile(seeded_database, database_path)
    value = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    yield value
    value.dispose()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    settings = Settings(database_url="sqlite:///:memory:", environment="test")
    with TestClient(create_app(settings=settings, engine=engine)) as value:
        yield value
