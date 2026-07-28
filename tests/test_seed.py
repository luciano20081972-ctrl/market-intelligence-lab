import hashlib
from pathlib import Path

from sqlalchemy import select

from packages.database.base import Base
from packages.database.models import Asset, PriceBar
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.market_data.seed import BAR_COUNT_PER_ASSET, seed_demonstration_data


def _seed_digest(path: Path) -> tuple[str, dict[str, int], dict[str, int]]:
    engine = create_database_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        first = seed_demonstration_data(session)
    with session_scope(factory) as session:
        second = seed_demonstration_data(session)
        rows = session.execute(
            select(Asset.symbol, PriceBar.event_time, PriceBar.close, PriceBar.volume)
            .join(PriceBar)
            .order_by(Asset.symbol, PriceBar.event_time)
        ).all()
    digest = hashlib.sha256(repr(rows).encode()).hexdigest()
    engine.dispose()
    return digest, first, second


def test_seed_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    digest_a, first, second = _seed_digest(tmp_path / "a.db")
    digest_b, _, _ = _seed_digest(tmp_path / "b.db")
    assert digest_a == digest_b
    assert first == {"assets_inserted": 9, "bars_inserted": 9 * BAR_COUNT_PER_ASSET}
    assert second == {"assets_inserted": 0, "bars_inserted": 0}
