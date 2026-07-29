# Provider framework

The framework defines capability protocols for historical OHLCV, corporate actions, asset metadata, and exchange calendars. ProviderRegistry rejects duplicate provider codes and returns deterministic registrations.

The deterministic synthetic adapter is enabled for local tests and Stooq is enabled for explicit read-only daily imports. Alpha Vantage, Twelve Data, Polygon, Financial Modeling Prep, Tiingo, and Yahoo Finance remain placeholders that are disabled by default and raise a safe disabled-provider error without making a network request. Database provider rows expose capability, health, enablement, last synchronization, and environment-variable reference metadata. API responses never include secret values.

A production adapter must normalize into the dataclasses in packages/market_data/types.py, use timezone-aware timestamps, implement bounded requests and retry classification, and pass the same ingestion validation path.
# Operational provider: Stooq

Stooq now implements daily historical OHLCV and symbol-only asset metadata. It requires no key, normalizes US symbols with `.us`, uses a fixed HTTPS endpoint, and supports one bounded non-paginated CSV request per symbol. Timeouts, 429, 5xx, malformed/empty/oversized responses, field mapping, source timestamps, row metadata, and checksums are normalized at the adapter boundary.

The provider does not expose reliable adjustment semantics through this adapter, corporate actions, or an exchange calendar. Adjusted-only requests are therefore rejected rather than mislabeled. Licensing and redistribution must be reviewed independently; enabling the adapter is not a licensing assertion. Other external registrations remain disabled placeholders.
