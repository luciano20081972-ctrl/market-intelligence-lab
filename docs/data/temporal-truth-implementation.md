# Temporal Truth implementation

Temporal Truth is an immutable seven-clock envelope:

| Clock | Meaning |
|---|---|
| `event_time` | When the represented event occurred. |
| `observation_time` | Period/date to which the value belongs. |
| `publication_time` | Earliest source publication known to the adapter. |
| `retrieval_time` | When this system acquired the bytes. |
| `effective_time` | When the fact applies economically or legally. |
| `revision_time` | When this vintage became the source's revision. |
| `simulation_eligible_time` | Conservative earliest time a simulation may use the record. |

All clocks are timezone-aware UTC. Eligibility must be at least the maximum of publication, retrieval, and revision. A point-in-time query first filters `simulation_eligible_time <= as_of`, then chooses the greatest visible revision per observation period. Reversing those operations leaks future revisions.

Precision and source timezone are explicit. Unknown publication time is not silently inferred from event time: adapters use retrieval time as a conservative floor and add `temporal_ambiguity` when the source cannot establish a more precise historical availability time.

The standard flags are `missing`, `revised`, `estimated`, `preliminary`, `outlier`, `duplicate`, `malformed`, `stale`, `unit_mismatch`, and `temporal_ambiguity`.

Source requirements are centralized: SEC requires accepted/filing/retrieval clocks; FRED requires observation/retrieval; ALFRED additionally requires realtime start/end; EIA requires period/retrieval. The validation suite proves future vintages are excluded.
