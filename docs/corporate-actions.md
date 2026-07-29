# Corporate actions

Supported event types are stock split, reverse split, dividend, and symbol change. Validation requires positive split ratios, nonnegative dividend amounts with currency, and old/new symbols for symbol changes.

Raw closes are preserved. Backward-adjusted closes apply earlier splits by division and earlier cash dividends by subtraction with a positive floor. Each action preserves provider, original symbol, effective/publication/retrieval times, checksum, and version. Production use requires provider-specific interpretation and licensed source data.
