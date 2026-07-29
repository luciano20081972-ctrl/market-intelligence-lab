# Real market data

Version 0.4.0 selects Stooq as the first operational external provider. It is read-only, needs no API key, and exposes bounded daily CSV OHLCV history at a fixed HTTPS endpoint. This makes local setup simple and keeps credentials out of the application. Stooq does not provide a service-level agreement, authoritative publication timestamps, intraday history through this adapter, or adjustment semantics sufficient to label the series adjusted.

The adapter maps `AAPL` to `aapl.us`, limits a request to 7,400 days and 2 MB, uses a configurable 1–60 second timeout, refuses redirects, and never accepts a caller-supplied URL. It normalizes HTTP 429 and temporary 5xx/network failures for durable retry. Empty, malformed, missing-value, and oversized responses fail without fabricated values. Retrieval time is used as publication time because the CSV has no publication timestamp. Each source row and aggregate batch has a SHA-256 checksum; the original provider symbol and source row are retained as non-secret JSON metadata.

No provider data is bundled. The project does not claim Stooq data is licensed for commercial redistribution. Review the provider’s current terms, attribution, retention, and redistribution requirements independently before any production or commercial use.

Ordinary tests use deterministic CSV fixtures and make no network requests. An optional manual smoke test makes exactly one small request:

```powershell
python scripts/operations.py provider-test --provider stooq
```

Run it only when external access is intentional. It requires no key.
