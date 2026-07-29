# Provider framework

The framework defines capability protocols for historical OHLCV, corporate actions, asset metadata, and exchange calendars. ProviderRegistry rejects duplicate provider codes and returns deterministic registrations.

The deterministic synthetic adapter is enabled for local tests. Alpha Vantage, Twelve Data, Polygon, Financial Modeling Prep, Tiingo, Stooq, and Yahoo Finance are placeholders that are disabled by default and raise a safe disabled-provider error without making a network request. Database provider rows expose capability, health, enablement, last synchronization, and environment-variable reference metadata. API responses never include secret values.

A production adapter must normalize into the dataclasses in packages/market_data/types.py, use timezone-aware timestamps, implement bounded requests and retry classification, and pass the same ingestion validation path.
