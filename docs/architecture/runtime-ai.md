# Runtime AI architecture

## Separation of responsibility

| Layer | Responsibility | Explicit non-responsibility |
|---|---|---|
| Codex | Develop, test, review, migrate, and maintain the factory | Continuous production research or world-data ingestion |
| Runtime application | Ingestion, jobs, storage, temporal truth, identity, features, policies, budgets | Unbounded autonomous reasoning |
| Runtime AI | Evidence extraction, candidate relationships/hypotheses, synthesis, counterarguments | Signal acceptance, temporal authority, direct orders, code self-modification |
| Quantitative engines | Statistics, ML, backtests, optimization, risk, calibration | Treating prose confidence as empirical evidence |

## Provider-neutral gateway

Domain services call an internal `ReasoningProvider` contract with task type, JSON schema, evidence IDs, temporal cutoff, maximum tokens/cost, retention class, allowed tools, and deadline. Responses include structured output, provider/model snapshot, prompt/template hash, request/response hashes, usage, latency, safety status, and cited evidence IDs. Provider payloads never become domain records directly.

Adapters may target the OpenAI Responses API, a locally hosted OpenAI-compatible or native inference server, or other approved providers. Store provider-independent task/result schemas and golden evaluations. No prompt assumes a proprietary built-in tool; retrieval and source access remain MIL services.

## Routing recommendation

- Local/small models: classification, deduplication, candidate extraction, low-risk reranking after evaluation.
- Hosted high-capability model: difficult relationship synthesis, hypothesis/counterargument generation, bounded dossiers.
- Deterministic code: identity, time, calculations, policy, feature generation, and gates.
- Asynchronous/batch path: non-urgent corpus extraction and evaluation; interactive path only for small reviewed packets.

For an OpenAI adapter, the Responses API supports structured/tool-enabled calls and the Batch API supports asynchronous `/v1/responses` work; retention and Zero Data Retention compatibility must be evaluated per task. Do not send secrets, restricted source text, or unapproved personal data. Official references: [API quickstart](https://platform.openai.com/docs/quickstart), [Batch API](https://platform.openai.com/docs/api-reference/batch), [data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint).

## Controls and evaluation

- Evidence allowlists, tenant isolation, prompt-injection-resistant parsing, output schemas, timeouts, retries, circuit breakers, and per-task budgets.
- Model/prompt changes pass golden extraction, citation, temporal, hallucination, abstention, cost, and adversarial suites.
- Claims without resolvable evidence are rejected or labeled unsupported.
- Reliability is calibrated by task/sector/regime from later outcomes and reviewer findings.
- A provider outage degrades AI features; ingestion, APIs, simulations, and stored research continue.
