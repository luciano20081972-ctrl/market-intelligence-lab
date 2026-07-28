from packages.core.config import get_settings
from packages.database.session import create_database_engine, make_session_factory, session_scope
from packages.market_data.seed import seed_demonstration_data


def main() -> None:
    settings = get_settings()
    settings.ensure_runtime_directories()
    factory = make_session_factory(create_database_engine(settings.database_url))
    with session_scope(factory) as session:
        result = seed_demonstration_data(session)
    print(
        f"Demonstration seed complete: {result['assets_inserted']} assets and "
        f"{result['bars_inserted']} bars inserted."
    )


if __name__ == "__main__":
    main()
