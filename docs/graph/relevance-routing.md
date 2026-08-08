# Data relevance routing

The v0.8 router is deterministic after profile construction. Dataset domains are versioned in `config/dataset-domains.yaml`; current official foundations are SEC, FRED, ALFRED, and EIA, while NOAA, USDA, FAA, and Commerce entries document catalogued domains without claiming live integrations.

For each company/dataset pair the router emits PROCESS, DEFER, IGNORE, or REVIEW with relevance score, reason codes, supporting graph paths, confidence, router version, and creation time. Evidence and explicit overrides can move a decision away from its sector prior. Basic routing requires no runtime LLM call.

PROCESS means current evidence supports ingestion. DEFER preserves plausible but lower-priority coverage. IGNORE avoids irrelevant processing. REVIEW captures uncertainty or conflict. Every positive decision can be explained through entity/relationship paths; a series link uses an intermediate economic mechanism rather than asserting that a company depends directly on a dataset.
