from __future__ import annotations

import os

import pytest

from packages.sec_intelligence import EdgarToolsSecAdapter, FixtureSecAdapter
from packages.sec_intelligence.adapters import (
    normalize_accession,
    normalize_cik,
    payload_checksum,
)


def test_fixture_parses_supported_forms_and_xbrl() -> None:
    payload = FixtureSecAdapter().import_company("320193", ("10-K", "4", "13F-HR"))
    assert payload["company"]["cik"] == "0000320193"
    assert {item["form_type"] for item in payload["filings"]} == {"10-K", "4", "13F-HR"}
    assert payload["facts"][0]["concept"] == "Revenues"
    assert payload["insider_transactions"][0]["transaction_code"] == "A"
    assert payload["institutional_holdings"][0]["cusip"] == "123456789"
    assert len(payload["checksum"]) == 64


def test_accession_cik_amendment_and_checksum_normalization() -> None:
    assert normalize_cik("CIK 320193") == "0000320193"
    assert normalize_accession("000032019326000001") == "0000320193-26-000001"
    assert payload_checksum({"b": 2, "a": 1}) == payload_checksum({"a": 1, "b": 2})
    payload = FixtureSecAdapter().import_company("0000320193", ("10-K",))
    assert payload["filings"][0]["is_amendment"] is False
    with pytest.raises(ValueError, match="18 digits"):
        normalize_accession("123")


def test_fixture_rejects_unknown_form_and_malformed_company() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        FixtureSecAdapter().import_company("320193", ("S-1",))
    with pytest.raises(ValueError, match="unavailable"):
        FixtureSecAdapter().import_company("1", ("10-K",))


def test_live_adapter_requires_responsible_identity_and_worker_gate() -> None:
    with pytest.raises(ValueError, match="identify"):
        EdgarToolsSecAdapter(user_agent="anonymous", requests_per_second=4, timeout_seconds=10)
    adapter = EdgarToolsSecAdapter(
        user_agent="Market Intelligence Lab research@example.invalid",
        requests_per_second=4,
        timeout_seconds=10,
    )
    with pytest.raises(RuntimeError, match="opt-in"):
        adapter.import_company("320193", ("10-K",))


@pytest.mark.live_sec
@pytest.mark.skipif(
    os.getenv("MIL_RUN_LIVE_SEC_TESTS", "").lower() != "true",
    reason="bounded live SEC verification is explicitly opt-in",
)
def test_live_sec_gate_is_explicit() -> None:
    pytest.skip("Live SEC worker transport is not configured in this release environment")
