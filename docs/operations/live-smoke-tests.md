# Live smoke tests

Live checks are opt-in through existing provider-specific environment flags. Keep requests few,
read-only, schema-validating, and compliant with provider rate/user-agent policies. Never use live
smokes in default CI and never invent credentials. A failure records sanitized classification and
does not print request headers, tokens, keys, cookies, or database URLs.
