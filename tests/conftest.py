import os
import shutil
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

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
    postgres_url = os.getenv("MIL_AUTH04_DATABASE_URL")
    if postgres_url:
        # Explicit opt-in, disposable DB only; every test gets a fresh schema.
        assert make_url(postgres_url).database == "mil_auth04b"
        schema = "case_" + uuid.uuid4().hex
        admin = create_engine(postgres_url, hide_parameters=True)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        value = create_engine(
            # Keep schema isolation when worker tests reconstruct engine.url.
            make_url(postgres_url).update_query_dict({"options": f"-csearch_path={schema}"}),
            hide_parameters=True,
        )
        try:
            Base.metadata.create_all(value)
            with make_session_factory(value).begin() as session:
                seed_demonstration_data(
                    session, calendar_start=date(2025, 1, 1), calendar_end=date(2027, 12, 31)
                )
            yield value
        finally:
            value.dispose()
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
        return
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
