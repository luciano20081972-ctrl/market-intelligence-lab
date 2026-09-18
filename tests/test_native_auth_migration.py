"""Disposable migration and cross-process acceptance; never uses production URLs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, inspect, select
from sqlalchemy.engine import make_url

from packages.auth import native
from packages.core.config import Settings, get_settings
from packages.core.time import utc_now
from packages.database.base import Base
from packages.database.models import (
    LEGACY_USER_ID,
    AuditEvent,
    BacktestRun,
    PaperPortfolio,
    Strategy,
    StrategyVersion,
    UserProfile,
    Watchlist,
)
from packages.database.session import create_database_engine, make_session_factory

PRESERVED = (
    "user_profiles",
    "workspaces",
    "workspace_memberships",
    "watchlists",
    "strategies",
    "strategy_versions",
    "backtest_runs",
    "paper_portfolios",
    "audit_events",
)


def exercise_migration(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIL_DATABASE_URL", url)
    monkeypatch.delenv("MIL_MIGRATION_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    engine = create_database_engine(url)
    assert not inspect(engine).get_table_names(), "Requires an empty disposable database"
    factory = make_session_factory(engine)
    command.upgrade(config, "a141c0de0001")
    with factory.begin() as session:
        session.get(UserProfile, LEGACY_USER_ID).auth_subject = "retained-external-subject"
        strategy = Strategy(
            name="Auth preservation", strategy_type="buy_and_hold", description="fixture"
        )
        session.add(strategy)
        session.flush()
        version = StrategyVersion(
            strategy_id=strategy.id,
            version=1,
            parameters={},
            parameter_schema={},
            calculation_notes="fixture",
        )
        session.add(version)
        session.flush()
        now = utc_now()
        session.add(
            BacktestRun(
                strategy_version_id=version.id,
                status="completed",
                asset_symbols=["TEST"],
                benchmark_symbol="TEST",
                start_time=now - timedelta(days=2),
                end_time=now,
                initial_cash=1000,
                cash_balance=1000,
                final_equity=1000,
                strategy_configuration={},
                risk_configuration={},
                execution_assumptions={},
                source_data_identifiers=[],
                data_source_identifiers=[],
                application_version="0.14.1",
            )
        )
        session.add(Watchlist(name="Preserved watchlist"))
        session.add(
            PaperPortfolio(name="Preserved paper state", starting_cash=1000, cash_balance=937)
        )
        session.add(
            AuditEvent(
                actor_user_id=LEGACY_USER_ID,
                action="fixture.preserved",
                entity_type="fixture",
                entity_id="before-native",
            )
        )

    def snapshot() -> dict[str, set[str]]:
        with engine.connect() as connection:
            return {
                name: {
                    repr(tuple(row))
                    for row in connection.execute(select(Base.metadata.tables[name]))
                }
                for name in PRESERVED
            }

    before = snapshot()
    assert all(before.values()), "Preservation checks must not be vacuous"
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    command.check(config)
    assert snapshot() == before
    inspector = inspect(engine)
    for name in ("native_credentials", "native_sessions", "auth_rate_buckets"):
        expected = {
            str(c.name)
            for c in Base.metadata.tables[name].constraints
            if isinstance(c, CheckConstraint)
        }
        assert {c["name"] for c in inspector.get_check_constraints(name)} == expected
        assert {
            i["name"] for i in inspector.get_indexes(name) if not i.get("duplicates_constraint")
        } == {i.name for i in Base.metadata.tables[name].indexes}
        assert inspector.get_pk_constraint(name)["name"] == f"pk_{name}"
    native.enroll(factory, engine, LEGACY_USER_ID, "owner", "disposable-enrollment-password")
    after = snapshot()
    for name in PRESERVED:
        assert (
            before[name] <= after[name] if name == "audit_events" else before[name] == after[name]
        )
    with factory() as session:
        assert native.ready(session)
    engine.dispose()
    get_settings.cache_clear()


def test_native_migration_preserves_application_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exercise_migration(f"sqlite:///{(tmp_path / 'native-migration.db').as_posix()}", monkeypatch)


@pytest.mark.postgres
def test_native_postgres_migration_and_cross_process(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.getenv("MIL_NATIVE_AUTH_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Explicit disposable native-auth PostgreSQL database required")
    assert (make_url(url).database or "").startswith("mil_auth02_")
    exercise_migration(url, monkeypatch)
    engine = create_database_engine(url)
    factory = make_session_factory(engine)
    settings = Settings(auth_mode="native", environment="test", database_url=url)
    token = native.login(
        factory, engine, settings, "owner", "disposable-enrollment-password", "test"
    )
    # JSON stdin keeps disposable tokens out of arguments and child tracebacks.
    program = """
import json,sys
from packages.auth import native,AuthError
from packages.core.config import Settings
from packages.database.session import create_database_engine,make_session_factory
data=json.load(sys.stdin)
engine=create_database_engine(data['url'])
try:
 native.authenticate(make_session_factory(engine),
  Settings(auth_mode='native'), 'Bearer '+data['token'])
 print('ACCEPTED')
except AuthError:
 print('REJECTED')
finally:
 engine.dispose()
"""

    def fresh() -> str:
        result = subprocess.run(
            [sys.executable, "-c", program],
            input=json.dumps({"url": url, "token": token}),
            text=True,
            capture_output=True,
            timeout=30,
            check=True,
        )
        return result.stdout.strip()

    assert fresh() == "ACCEPTED"
    principal = native.authenticate(factory, settings, f"Bearer {token}")
    native.logout(factory, principal)
    assert fresh() == "REJECTED"
    # Separate interpreter must fail to acquire either global PostgreSQL hash slot.
    busy_program = """
import json,sys
from packages.auth import native
from packages.database.session import create_database_engine
engine=create_database_engine(json.load(sys.stdin)['url'])
try:
 with native.hash_slot(engine): print('UNBOUNDED')
except native.AuthBusy: print('BOUNDED')
finally: engine.dispose()
"""
    with native.hash_slot(engine), native.hash_slot(engine):
        result = subprocess.run(
            [sys.executable, "-c", busy_program],
            input=json.dumps({"url": url}),
            text=True,
            capture_output=True,
            timeout=30,
            check=True,
        )
        assert result.stdout.strip() == "BOUNDED"
    engine.dispose()
