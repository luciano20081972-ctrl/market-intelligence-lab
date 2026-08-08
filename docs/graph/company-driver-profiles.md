# Company driver profiles

A driver profile describes variables that may be economically relevant to one company. It is not a trading signal, causality finding, expected-return estimate, or investment recommendation.

Profiles combine versioned sector/industry priors from `config/driver-priors.yaml` with current evidence-backed graph relationships. Each entry records its category, linked entities, supporting relationships, prior relevance, evidence relevance, a reserved historical-validation field, optional user override, effective relevance, confidence, explanation, version, and simulation-eligibility time.

The three deterministic references deliberately differ: Silica Systems emphasizes technology, geopolitics, energy, supply chain, and regulation; Meridian Air emphasizes fuel/energy, weather, transportation/travel, and labor; Harvest Fields Cooperative emphasizes weather/environment, agriculture, water, energy, and inputs. These profiles demonstrate routing behavior only and make no investment prediction.

Relationship additions/expiry, facilities, segments, geography changes, and manual overrides enqueue durable `graph_recompute_jobs`. Reprocessing writes a new profile version and new routing decisions rather than mutating historical results.
