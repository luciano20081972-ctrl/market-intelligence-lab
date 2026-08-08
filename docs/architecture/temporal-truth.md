# Temporal Truth

## v0.8 graph integration

Economic entities, identifiers, aliases, resolution candidates, relationships, evidence, and profiles carry validity and/or simulation-eligibility clocks. Bounded graph queries require `simulation_eligible_time <= as_of`, `valid_from <= as_of`, and `valid_to IS NULL OR valid_to > as_of`. The half-open validity boundary prevents an expired relationship from appearing at its expiry instant. Tests prove that an edge discovered one second after a historical cutoff is absent, while it becomes visible at its eligibility time. Path evidence is filtered by the same eligibility cutoff.

Temporal correctness is a data contract, not a backtest option. Times are timezone-aware UTC instants unless a source provides only a date; date precision and timezone assumptions are stored separately.

## Standard envelope

| Field | Meaning | Required rule |
|---|---|---|
| `event_time` | When the underlying real-world event occurred | Nullable only when genuinely unknown. |
| `observation_time` | When a sensor, venue, filer, or observer recorded it | Never inferred silently from retrieval. |
| `publication_time` | First time the source made this version public | Required for public-information simulations. |
| `retrieval_time` | When MIL received this exact payload | Always required and server-stamped. |
| `effective_time` | When a rule, guidance item, contract, or fact applies economically/legalistically | May precede or follow publication. |
| `revision_time` | When this version superseded a prior value | Required for revisions; prior rows remain. |
| `simulation_eligible_time` | Earliest instant the normalized record may enter a historical simulation | Derived, persisted, explainable, never earlier than publication/retrieval constraints. |

Supporting fields: `source_timezone`, `time_precision`, `availability_policy_id`, `release_id`, `revision_number`, `supersedes_id`, `source_latency_assumption`, `embargo_end`, `market_session_id`, and `eligibility_reason`.

## Dataset application

| Data | Important mappings | Eligibility policy |
|---|---|---|
| Market prices | event=exchange timestamp; observation=feed timestamp; publication=vendor availability; retrieval=ingest | Max(publication, conservative feed delay); trade only on a subsequent permitted event/session. |
| SEC filings | event/effective may be report period; publication=EDGAR acceptance/dissemination; retrieval=fetch | EDGAR public dissemination plus parsing delay; never filing period end. |
| Economic releases | event=reference period; publication=release timestamp; revision=release/vintage time | Exact vintage publication; revised values create new eligible versions. |
| ALFRED-style macro | observation=reference date; publication/revision from real-time period | Query the vintage known at the simulated clock. |
| News/global events | event may differ from article time; publication=publisher timestamp; retrieval=collector | Max(verifiable publication, retrieval), with uncertainty flags for backfilled items. |
| Government actions | event=vote/signing/action; publication=official posting; effective=legal applicability | Public posting for awareness; effective time separately controls economic applicability. |
| Forecasts | event=forecast target; observation/publication=model run issuance | Forecast issuance time, never target-valid time or later reanalysis. |
| Weather observations | event/observation=sensor valid time; publication=archive availability | Operational observation availability; later QC/reanalysis is a revision. |
| Satellite observations | event=acquisition; publication=product availability; revision=reprocessing | Product release time plus processing latency; corrected collection is a new version. |
| Corporate guidance | event=meeting/call; publication=filing/release/broadcast; effective=guided period | First public channel time plus capture uncertainty. |
| Scientific work | event=study period if known; publication=preprint/deposit; revision=version date | Public preprint/deposit time for that version, not journal issue date if later. |

## Eligibility function

Conceptually:

```text
simulation_eligible_time = max(
  authoritative_public_availability,
  embargo_end,
  source_policy_minimum,
  required_processing_completion,
  conservative_unknown-time_floor
)
```

Retrieval is not always the historical availability time: a 2010 filing retrieved today was public in 2010. That earlier time must come from an authoritative source field and policy. If it cannot be established, the record is ineligible for historical simulation or is eligible only from retrieval.

## Invariants

- UTC-aware values only; precision and original representation are retained.
- `retrieval_time >= publication_time` for live capture, except approved historical backfills with a recorded policy.
- `revision_time >= publication_time` for the revision version.
- `valid_from < valid_to` when `valid_to` exists.
- A revision never mutates or deletes the superseded version.
- A feature's eligibility is at least the maximum eligibility of all inputs and the feature computation completion policy.
- A graph edge's eligibility is at least the maximum eligibility of its supporting evidence.
- A simulation query requires `simulation_eligible_time <= simulation_clock` and the version valid at that clock.
- Unknown publication time never defaults to event time.

## Required tests

1. Boundary tests one microsecond before/at eligibility.
2. SEC report-period versus dissemination-time regression.
3. Macro initial-release/revision vintage replay with different results at two simulation clocks.
4. Forecast issuance versus target/reanalysis leakage test.
5. Backfilled news with missing publication timestamp remains ineligible until retrieval.
6. Satellite acquisition versus product-publication/reprocessing test.
7. Derived feature takes the latest input eligibility.
8. Edge and dossier evidence cannot precede their newest supporting record.
9. DST/date-only/timezone ambiguity fixtures.
10. Property tests that no simulation output references a later input.

Each adapter must ship a temporal mapping specification and fixtures before it may be used in historical research.

Sources: [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [FRED real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html), [ALFRED](https://fred.stlouisfed.org/docs/api/fred/alfred.html), [NASA POWER revision note](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/).
