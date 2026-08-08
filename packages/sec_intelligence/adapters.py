from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
from datetime import UTC, datetime
from typing import Any

from packages.upstream.protocols import (
    UpstreamCapability,
    UpstreamHealthReport,
    UpstreamVersionInfo,
)

SUPPORTED_FORMS = frozenset({"10-K", "10-Q", "8-K", "3", "4", "5", "13F-HR"})
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
ADAPTER_VERSION = "1.0"

FIXTURE_PAYLOAD: dict[str, Any] = {
    "company": {
        "cik": "0000320193",
        "name": "Example Technology Inc.",
        "tickers": ["EXM"],
        "sic": "3571",
        "submissions_url": "https://data.sec.gov/submissions/CIK0000320193.json",
        "facts_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
    },
    "filings": [
        {
            "accession_number": "0000320193-26-000001",
            "form_type": "10-K",
            "filing_date": "2026-02-01",
            "accepted_at": "2026-02-01T21:15:00Z",
            "reporting_period": "2025-12-31",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/fixture-10k.htm",
            "raw_document_reference": "fixture://sec/0000320193-26-000001",
            "is_amendment": False,
        },
        {
            "accession_number": "0000320193-26-000002",
            "form_type": "4",
            "filing_date": "2026-02-03",
            "accepted_at": "2026-02-03T22:05:00Z",
            "reporting_period": "2026-02-02",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/fixture-form4.xml",
            "raw_document_reference": "fixture://sec/0000320193-26-000002",
            "is_amendment": False,
        },
        {
            "accession_number": "0000320193-26-000003",
            "form_type": "13F-HR",
            "filing_date": "2026-02-14",
            "accepted_at": "2026-02-14T19:30:00Z",
            "reporting_period": "2025-12-31",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/fixture-13f.xml",
            "raw_document_reference": "fixture://sec/0000320193-26-000003",
            "is_amendment": False,
        },
    ],
    "facts": [
        {
            "accession_number": "0000320193-26-000001",
            "taxonomy": "us-gaap",
            "concept": "Revenues",
            "unit": "USD",
            "numeric_value": "250000000.00",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "filed_at": "2026-02-01T21:15:00Z",
        }
    ],
    "insider_transactions": [
        {
            "accession_number": "0000320193-26-000002",
            "owner_name": "Jordan Example",
            "relationship": "Director",
            "transaction_code": "A",
            "security_title": "Common Stock",
            "transaction_date": "2026-02-02",
            "shares": "100.00000000",
            "price": "0",
            "acquired_disposed": "A",
        }
    ],
    "institutional_holdings": [
        {
            "accession_number": "0000320193-26-000003",
            "issuer_name": "Example Holdings Corp.",
            "cusip": "123456789",
            "as_of_date": "2025-12-31",
            "shares": "1200.0000",
            "value_usd": "180000.00",
            "voting_authority": {"sole": 1200, "shared": 0, "none": 0},
        }
    ],
}


def normalize_cik(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if not digits or len(digits) > 10:
        raise ValueError("CIK must contain between 1 and 10 digits")
    return digits.zfill(10)


def normalize_accession(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) != 18:
        raise ValueError("Accession number must contain exactly 18 digits")
    normalized = f"{digits[:10]}-{digits[10:12]}-{digits[12:]}"
    if not ACCESSION_PATTERN.fullmatch(normalized):
        raise ValueError("Accession number is invalid")
    return normalized


def payload_checksum(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class FixtureSecAdapter:
    def health(self) -> UpstreamHealthReport:
        return UpstreamHealthReport(
            status="healthy",
            available=True,
            capabilities=tuple(
                UpstreamCapability(form.lower(), f"Parse SEC form {form}", True)
                for form in sorted(SUPPORTED_FORMS)
            ),
            version=UpstreamVersionInfo("edgartools", ADAPTER_VERSION, "fixture", None),
            message="Deterministic fixture adapter; no network access",
        )

    def import_company(self, cik: str, forms: tuple[str, ...]) -> dict[str, Any]:
        normalized = normalize_cik(cik)
        requested = set(forms)
        if requested - SUPPORTED_FORMS:
            raise ValueError("One or more SEC forms are unsupported")
        if normalized != FIXTURE_PAYLOAD["company"]["cik"]:
            raise ValueError("Fixture CIK is unavailable")
        payload = json.loads(json.dumps(FIXTURE_PAYLOAD))
        payload["filings"] = [
            item for item in payload["filings"] if not requested or item["form_type"] in requested
        ]
        accepted = {item["accession_number"] for item in payload["filings"]}
        for key in ("facts", "insider_transactions", "institutional_holdings"):
            payload[key] = [
                item for item in payload[key] if item["accession_number"] in accepted
            ]
        payload["retrieved_at"] = datetime(2026, 3, 1, 12, tzinfo=UTC).isoformat()
        payload["checksum"] = payload_checksum(payload)
        payload["edgartools_version"] = "5.43.1-fixture"
        payload["parser_version"] = ADAPTER_VERSION
        return payload


class EdgarToolsSecAdapter:
    """Optional live boundary; ordinary tests never make network calls."""

    def __init__(
        self, *, user_agent: str, requests_per_second: float, timeout_seconds: float
    ) -> None:
        if "@" not in user_agent or len(user_agent.strip()) < 8:
            raise ValueError("SEC user agent must identify the application and a contact")
        if not 0 < requests_per_second <= 10:
            raise ValueError("SEC request rate must be between 0 and 10 requests per second")
        self.user_agent = user_agent
        self.requests_per_second = requests_per_second
        self.timeout_seconds = timeout_seconds

    def health(self) -> UpstreamHealthReport:
        try:
            version = importlib.metadata.version("edgartools")
        except importlib.metadata.PackageNotFoundError:
            version = None
        return UpstreamHealthReport(
            status="available" if version else "unavailable",
            available=version is not None,
            capabilities=(
                UpstreamCapability("company_submissions", "Company submissions", True),
                UpstreamCapability("company_facts", "XBRL company facts", True),
                UpstreamCapability("live_sec", "Bounded live SEC retrieval", False),
            ),
            version=UpstreamVersionInfo("edgartools", ADAPTER_VERSION, version, None),
            message=(
                "Live adapter dependency is available"
                if version
                else "Install the integrations extra to enable bounded live SEC retrieval"
            ),
        )

    def import_company(self, cik: str, forms: tuple[str, ...]) -> dict[str, Any]:
        raise RuntimeError(
            "Live SEC import is opt-in and must run through the bounded ingestion worker"
        )
