# Research Memory

Research Memory converts a completed v0.10 experiment into an immutable lesson only after a final out-of-sample fold exists. Each entry retains the hypothesis and mechanism checksums, exact feature/outcome versions, graph path, datasets, validation summary, failure reasons, provenance, and the time at which the lesson became simulation-eligible.

Positive and negative results are equal scientific records. Search supports exact mechanism/feature/outcome matching and applicability filters. As-of retrieval excludes knowledge that was not available at the simulated time. Mutable lifecycle fields are limited to status, last confirmation, and append-only provenance; weakening does not rewrite the original conclusion.

The Hypothesis Factory classifies candidates as new, known success, known failure, or contradicted before expensive work. Known failures are suppressed by default. A materially justified override is explicit and audited; it does not erase the historical rejection.
