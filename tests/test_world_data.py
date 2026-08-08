import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from packages.database.models import MacroSeries
from packages.world_data.ingestion import ingest_macro_rows, persist_manifest, save_checkpoint
from packages.world_data.manifests import SourceManifest, sha256_bytes
from packages.world_data.object_store import LocalRawObjectStore, immutable_object_key
from packages.world_data.providers import (
    SecDirectAdapter,
    get_observation_as_of,
    normalize_accession,
    normalize_cik,
    parse_eia_electricity,
    parse_fred_observations,
)
from packages.world_data.registry import load_dataset_registry
from packages.world_data.temporal import QualityFlag, TemporalTruth

NOW = datetime(2026, 8, 7, 12, tzinfo=UTC)


def truth(**overrides: datetime) -> TemporalTruth:
    values = {
        "event_time": NOW - timedelta(days=10),
        "observation_time": NOW - timedelta(days=10),
        "publication_time": NOW - timedelta(days=5),
        "retrieval_time": NOW - timedelta(days=4),
        "effective_time": NOW - timedelta(days=10),
        "revision_time": NOW - timedelta(days=5),
        "simulation_eligible_time": NOW - timedelta(days=4),
    }
    values.update(overrides)
    return TemporalTruth(**values)


def test_01_temporal_truth_normalizes_offsets_to_utc() -> None:
    value = truth(event_time=datetime.fromisoformat("2026-08-07T08:00:00-04:00"))
    assert value.event_time == NOW


def test_02_naive_temporal_values_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        truth(event_time=datetime(2026, 1, 1))


def test_03_simulation_eligibility_cannot_precede_retrieval() -> None:
    with pytest.raises(ValidationError, match="simulation_eligible_time"):
        truth(simulation_eligible_time=NOW - timedelta(days=6))


def test_04_future_revisions_are_invisible_as_of() -> None:
    value = truth(revision_time=NOW, simulation_eligible_time=NOW)
    assert not value.visible_as_of(NOW - timedelta(seconds=1))


def test_05_publication_delay_controls_eligibility() -> None:
    with pytest.raises(ValidationError):
        truth(publication_time=NOW, simulation_eligible_time=NOW - timedelta(hours=1))


def test_06_manifest_is_immutable_and_identifiers_are_safe() -> None:
    manifest = SourceManifest(
        source_id="fred", dataset_id="fred.observations", parser_version="0.7.0",
        retrieval_time=NOW, raw_object_reference="fred/observations/2026/08/07/a",
        checksum="a" * 64, byte_count=1, record_count=1, accepted_count=1,
        rejected_count=0, license_identifier="FRED-SERIES-SPECIFIC",
    )
    with pytest.raises(ValidationError):
        SourceManifest(**{**manifest.model_dump(), "dataset_id": "../unsafe"})
    with pytest.raises(ValidationError):
        manifest.record_count = 2  # type: ignore[misc]


def test_07_raw_object_store_is_immutable_and_checksum_verified(tmp_path: Path) -> None:
    store = LocalRawObjectStore(tmp_path)
    key = immutable_object_key("fred", "observations", NOW, "abc.json")
    first = store.put(key, b"payload", "application/json")
    second = store.put(key, b"payload", "application/json")
    assert first == second and store.verify_checksum(key)
    with pytest.raises(FileExistsError):
        store.put(key, b"changed", "application/json")


def test_08_registry_covers_all_approved_official_sources() -> None:
    ids = {item.id for item in load_dataset_registry().datasets}
    assert {"sec.submissions", "sec.companyfacts", "sec.bulk", "fred.observations",
            "alfred.vintages", "eia.electricity.retail-price"} <= ids


def test_09_sec_identifiers_are_canonical() -> None:
    assert normalize_cik("320193") == "0000320193"
    assert normalize_accession("0000320193-26-000001") == "0000320193-26-000001"


def test_10_sec_amendments_and_accepted_time_are_preserved() -> None:
    payload = json.dumps({"cik": 320193, "filings": {"recent": {
        "accessionNumber": ["0000320193-26-000001"], "form": ["10-K/A"],
        "acceptanceDateTime": ["2026-08-01T14:30:00Z"], "filingDate": ["2026-08-01"]
    }}}).encode()
    row = SecDirectAdapter.parse_submissions(payload, NOW)[0]
    assert row["is_amendment"] is True
    assert row["simulation_eligible_time"] == NOW


def test_11_fred_missing_values_are_explicitly_flagged() -> None:
    rows = parse_fred_observations(
        json.dumps({"observations": [{"date": "2026-01-01", "value": "."}]}).encode(),
        NOW, vintage=False,
    )
    assert rows[0]["value"] is None
    assert QualityFlag.MISSING in rows[0]["truth"].quality_flags


def test_12_alfred_as_of_selects_only_known_vintage() -> None:
    payload = json.dumps({"observations": [
        {"date": "2026-01-01", "value": "1.0", "realtime_start": "2026-02-01",
         "realtime_end": "2026-02-28"},
        {"date": "2026-01-01", "value": "2.0", "realtime_start": "2026-03-01",
         "realtime_end": "9999-12-31"},
    ]}).encode()
    rows = parse_fred_observations(payload, NOW, vintage=True)
    selected = get_observation_as_of(rows, datetime(2026, 2, 15, tzinfo=UTC))
    assert selected is None  # retrieval happened later, so neither vintage was yet known locally.


def test_13_alfred_latest_revision_does_not_leak_backward() -> None:
    payload = json.dumps({"observations": [
        {"date": "2026-01-01", "value": "1", "realtime_start": "2026-02-01"},
        {"date": "2026-01-01", "value": "9", "realtime_start": "2026-08-07"},
    ]}).encode()
    rows = parse_fred_observations(payload, datetime(2026, 2, 2, tzinfo=UTC), vintage=True)
    selected = get_observation_as_of(rows, datetime(2026, 3, 1, tzinfo=UTC))
    assert selected is not None and selected["source_value"] == "1"


def test_14_eia_pilot_preserves_units_geography_and_month_precision() -> None:
    payload = json.dumps({"response": {"data": [{
        "period": "2026-01", "price": "12.34", "price-units": "cents/kWh", "stateid": "US"
    }]}}).encode()
    row = parse_eia_electricity(payload, NOW)[0]
    assert (row["units"], row["geography"], row["truth"].precision) == (
        "cents/kWh", "US", "month"
    )


def test_payload_checksum_is_deterministic() -> None:
    assert sha256_bytes(b"same") == sha256_bytes(b"same")


def test_world_data_registry_api(client: object) -> None:
    response = client.get("/api/v1/data-sources")  # type: ignore[attr-defined]
    assert response.status_code == 200
    assert len(response.json()) == 6


def test_manifest_observation_and_checkpoint_replay_is_idempotent(engine: object) -> None:
    payload = json.dumps({"observations": [{
        "date": "2026-01-01", "value": "3.2", "realtime_start": "2026-02-01"
    }]}).encode()
    definition = SourceManifest(
        source_id="alfred", dataset_id="alfred.vintages", parser_version="0.7.0",
        retrieval_time=NOW, raw_object_reference="alfred/vintages/2026/08/07/object.json",
        checksum=sha256_bytes(payload), byte_count=len(payload), record_count=1,
        accepted_count=1, rejected_count=0, license_identifier="FRED-SERIES-SPECIFIC",
    )
    with Session(engine) as session:  # type: ignore[arg-type]
        manifest, created = persist_manifest(session, definition)
        same_manifest, created_again = persist_manifest(session, definition)
        assert created is True and created_again is False and same_manifest.id == manifest.id
        series = MacroSeries(
            source_id="alfred", external_id="TEST", title="Fixture", units="Index",
            frequency="Monthly", retrieved_at=NOW,
        )
        rows = parse_fred_observations(payload, NOW, vintage=True)
        assert ingest_macro_rows(session, series, rows, manifest.id) == (1, 0)
        assert ingest_macro_rows(session, series, rows, manifest.id) == (0, 1)
        checkpoint = save_checkpoint(
            session, "alfred", "alfred.vintages", {"offset": 1}, manifest.id
        )
        resumed = save_checkpoint(session, "alfred", "alfred.vintages", {"offset": 2}, manifest.id)
        assert resumed.id == checkpoint.id and resumed.cursor_json == {"offset": 2}
        session.rollback()
