# Identifier resolution

`entity_identifiers` provides unique workspace mappings for normalized namespace/value pairs. Initial namespaces include internal asset ID, ticker, exchange, CIK, LEI, ISO country, FIPS, provider series ID, and source-specific facility IDs. Normalizers are namespace-aware and preserve the original value for display and audit.

Exact or normalized matches may resolve deterministically. Competing mappings become `entity_resolution_candidates`; they are never silently merged. An administrator may confirm or reject a candidate through the protected API, creating an immutable `entity_resolution_decisions` record with reason, actor, and time. Confirmations cannot replace an existing conflicting identifier.

Each identifier/candidate records method, confidence, source, evidence reference or structured evidence, resolver version, resolution time, validity interval, and simulation-eligibility time. Database uniqueness is the final concurrency guard.
