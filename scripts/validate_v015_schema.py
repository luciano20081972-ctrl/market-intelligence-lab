"""Read-only verification of the v0.15 revision and reflected check constraints."""

from __future__ import annotations

import json

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, inspect, text

from packages.database.base import Base
from packages.database.session import create_database_engine


def main() -> None:
    engine = create_database_engine()
    try:
        with engine.connect() as connection:
            heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
            revisions = list(connection.scalars(text("SELECT version_num FROM alembic_version")))
            assert heads == revisions == ["f01500000001"], (heads, revisions)
            checks = {}
            for table in ("asset_listings", "asset_identifiers", "provider_asset_mappings"):
                expected = {
                    connection.dialect.identifier_preparer.format_constraint(constraint)
                    for constraint in Base.metadata.tables[table].constraints
                    if isinstance(constraint, CheckConstraint)
                }
                actual = {row["name"] for row in inspect(connection).get_check_constraints(table)}
                assert actual == expected, (table, actual, expected)
                checks[table] = sorted(actual)
            version = connection.scalar(text("SELECT version()"))
            print(json.dumps({"version": version, "heads": heads, "checks": checks}, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
