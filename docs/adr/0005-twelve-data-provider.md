# ADR 0005: Twelve Data as the second historical provider

Status: accepted for fixture-tested integration
Verified: 2026-07-30 against official documentation and pricing; terms require review before production.

## Decision

Use Twelve Data's documented HTTPS `/time_series` API as the second daily OHLCV adapter. The fixed host, JSON schema, header-based `Authorization: apikey …` authentication, daily interval, bounded dates, U.S. stock/ETF coverage, explicit `adjust=all|splits|dividends|none`, and documented 429 behavior fit the existing provider interface. The Basic page listed 8 credits/minute and 800/day for internal non-display use on the verification date. This is not a grant of commercial display or redistribution rights.

Official sources: [API overview](https://twelvedata.com/docs/introduction/overview), [authentication and errors](https://twelvedata.com/docs/introduction/quickstart), [pricing](https://twelvedata.com/pricing).

## Alternatives

| Provider | Evidence reviewed | Reason not selected now |
|---|---|---|
| Alpha Vantage | Official API and terms pages | Documented daily endpoints are viable, but quota and licensing fit must be rechecked for the intended deployment. |
| Tiingo | Official EOD documentation and pricing | Strong raw/adjusted and correction semantics; deferred pending account/terms review. |
| Financial Modeling Prep | Official developer and pricing pages | Viable documented EOD endpoints; plan entitlement and redistribution review remain open. |
| Stooq | Existing fixed CSV adapter | Remains degraded/unknown: the permitted live check returned an HTML access page, not bars. |

## Boundaries and exit

Keys come only from `MIL_TWELVE_DATA_API_KEY`; the adapter uses an allowlisted HTTPS host, header authentication, timeouts, response limits, strict schema/value validation, checksums, and normalized errors. Tests use fixtures. Live smoke testing is opt-in and was not run for this release. Canonical SQLAlchemy models and exportable bars avoid vendor object lock-in; another `MarketDataAdapter` can replace it.
