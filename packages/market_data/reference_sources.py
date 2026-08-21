from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.time import utc_now
from packages.database.models import (
    Asset,
    AssetCapability,
    AssetIdentifier,
    AssetListing,
    Issuer,
    ReferenceObservation,
)
from packages.market_data.types import (
    ProviderAccessDeniedError,
    ProviderContentTypeError,
    ProviderHtmlResponseError,
    ProviderNetworkError,
    ProviderResponseTooLargeError,
    ProviderSchemaError,
    ProviderTemporaryError,
)

REFERENCE_NAMESPACE = uuid.UUID("6deba63c-7f82-40cc-ae06-a01d58ba214f")
NASDAQ_URLS = {
    "nasdaq": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "other": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
EXCLUDED_NAME_PATTERNS = (
    re.compile(r"\bWARRANTS?\b", re.IGNORECASE),
    re.compile(r"\bRIGHTS?\b", re.IGNORECASE),
    re.compile(r"\bUNITS?\b", re.IGNORECASE),
    re.compile(r"\bPREFERRED\b", re.IGNORECASE),
)
MIC_BY_EXCHANGE = {
    "NASDAQ": "XNAS",
    "NYSE": "XNYS",
    "NYSE AMERICAN": "XASE",
    "NYSE ARCA": "ARCX",
    "CBOE": "BATS",
    "IEX": "IEXG",
}
OTHER_EXCHANGE = {
    "A": ("NYSE AMERICAN", "XASE"),
    "N": ("NYSE", "XNYS"),
    "P": ("NYSE ARCA", "ARCX"),
    "Z": ("CBOE", "BATS"),
    "V": ("IEX", "IEXG"),
}


@dataclass(frozen=True)
class ReferenceSecurityRecord:
    source: str
    source_record_key: str
    symbol: str
    security_name: str
    exchange_code: str
    mic: str | None
    asset_type: str
    is_active: bool
    is_test_issue: bool
    is_etf: bool
    cik: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def checksum(self) -> str:
        normalized = {
            "source": self.source,
            "source_record_key": self.source_record_key,
            "symbol": self.symbol,
            "security_name": self.security_name,
            "exchange_code": self.exchange_code,
            "mic": self.mic,
            "asset_type": self.asset_type,
            "is_active": self.is_active,
            "is_test_issue": self.is_test_issue,
            "is_etf": self.is_etf,
            "cik": self.cik,
            "metadata": self.metadata,
        }
        return hashlib.sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def eligibility(record: ReferenceSecurityRecord) -> tuple[str, str | None]:
    if record.is_test_issue:
        return "EXCLUDED", "TEST_ISSUE"
    if record.mic not in set(MIC_BY_EXCHANGE.values()):
        return "EXCLUDED", "UNSUPPORTED_EXCHANGE"
    if record.asset_type not in {"equity", "etf"}:
        return "EXCLUDED", "UNSUPPORTED_SECURITY_TYPE"
    for pattern in EXCLUDED_NAME_PATTERNS:
        if pattern.search(record.security_name):
            return "EXCLUDED", pattern.pattern.strip("\\b").upper()
    return "ELIGIBLE", None


class _ReferenceHttpClient:
    max_response_bytes = 8_000_000

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 20,
        user_agent: str = "Market Intelligence Lab admin@example.invalid",
    ) -> None:
        if timeout_seconds < 1 or timeout_seconds > 60:
            raise ValueError("Reference-source timeout must be between 1 and 60 seconds")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def _get(self, url: str, *, media_types: set[str]) -> bytes:
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=False,
                headers={"Accept": ", ".join(sorted(media_types)), "User-Agent": self.user_agent},
            ) as client:
                response = client.get(url)
        except httpx.RequestError as exc:
            raise ProviderNetworkError("Reference source was unavailable") from exc
        if response.status_code in {401, 403}:
            raise ProviderAccessDeniedError("Reference source denied the bounded request")
        if response.status_code >= 500:
            raise ProviderTemporaryError("Reference source is temporarily unavailable")
        if response.status_code != 200:
            raise ProviderSchemaError("Reference source returned an unexpected status")
        if len(response.content) > self.max_response_bytes:
            raise ProviderResponseTooLargeError("Reference response exceeded the size limit")
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type and content_type not in media_types:
            raise ProviderContentTypeError("Reference source returned an unexpected content type")
        if response.content.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            raise ProviderHtmlResponseError("Reference source returned an HTML access page")
        return response.content


class NasdaqReferenceAdapter(_ReferenceHttpClient):
    code = "nasdaq_trader"
    name = "Nasdaq Trader Symbol Directory"

    def fetch(self) -> list[ReferenceSecurityRecord]:
        records: list[ReferenceSecurityRecord] = []
        for dataset, url in NASDAQ_URLS.items():
            payload = self._get(
                url,
                media_types={"text/plain", "text/csv", "application/octet-stream", ""},
            )
            records.extend(self.parse(dataset, payload))
        return records

    @staticmethod
    def parse(dataset: str, payload: bytes) -> list[ReferenceSecurityRecord]:
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ProviderSchemaError("Nasdaq directory was not UTF-8 compatible") from exc
        reader = csv.DictReader(io.StringIO(text), delimiter="|")
        if dataset == "nasdaq":
            required = {"Symbol", "Security Name", "Test Issue", "ETF"}
        elif dataset == "other":
            required = {"ACT Symbol", "Security Name", "Exchange", "Test Issue", "ETF"}
        else:
            raise ValueError("Unknown Nasdaq directory dataset")
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ProviderSchemaError("Nasdaq directory omitted required fields")
        records: list[ReferenceSecurityRecord] = []
        for row in reader:
            first = str(next(iter(row.values()), "")).strip()
            if not first or first.startswith("File Creation Time"):
                continue
            symbol = str(
                row["Symbol"] if dataset == "nasdaq" else row["ACT Symbol"]
            ).strip().upper()
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-$]{0,30}", symbol):
                continue
            exchange_code: str
            mic: str | None
            if dataset == "nasdaq":
                exchange_code, mic = "NASDAQ", "XNAS"
            else:
                exchange_code, mic = OTHER_EXCHANGE.get(
                    str(row["Exchange"]).strip(), ("OTHER", None)
                )
            is_etf = str(row.get("ETF", "N")).strip().upper() == "Y"
            records.append(
                ReferenceSecurityRecord(
                    source=f"nasdaq_trader:{dataset}",
                    source_record_key=f"{dataset}:{symbol}",
                    symbol=symbol,
                    security_name=str(row["Security Name"]).strip(),
                    exchange_code=exchange_code,
                    mic=mic,
                    asset_type="etf" if is_etf else "equity",
                    is_active=True,
                    is_test_issue=str(row.get("Test Issue", "N")).strip().upper() == "Y",
                    is_etf=is_etf,
                    metadata={
                        key: value for key, value in row.items() if key and value is not None
                    },
                )
            )
        if not records:
            raise ProviderSchemaError("Nasdaq directory contained no security records")
        return records


class SecCompanyTickerAdapter(_ReferenceHttpClient):
    code = "sec_company_tickers"
    name = "SEC Company Ticker and Exchange Reference"

    def fetch(self) -> list[ReferenceSecurityRecord]:
        payload = self._get(SEC_TICKERS_URL, media_types={"application/json", "text/json", ""})
        return self.parse(payload)

    @staticmethod
    def parse(payload: bytes) -> list[ReferenceSecurityRecord]:
        try:
            root = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderSchemaError("SEC ticker response was malformed JSON") from exc
        if (
            not isinstance(root, dict)
            or not isinstance(root.get("fields"), list)
            or not isinstance(root.get("data"), list)
        ):
            raise ProviderSchemaError("SEC ticker response schema was invalid")
        fields = [str(value) for value in root["fields"]]
        required = {"cik", "name", "ticker", "exchange"}
        if not required.issubset(fields):
            raise ProviderSchemaError("SEC ticker response omitted required fields")
        records: list[ReferenceSecurityRecord] = []
        for values in root["data"]:
            if not isinstance(values, list) or len(values) != len(fields):
                raise ProviderSchemaError("SEC ticker response contained a malformed row")
            row = dict(zip(fields, values, strict=True))
            symbol = str(row["ticker"]).strip().upper()
            exchange = str(row["exchange"]).strip().upper()
            exchange_code = {
                "NASDAQ": "NASDAQ", "NYSE": "NYSE", "NYSE AMERICAN": "NYSE AMERICAN",
                "NYSE ARCA": "NYSE ARCA", "CBOE": "CBOE", "IEX": "IEX",
            }.get(exchange, exchange or "OTHER")
            cik = str(row["cik"]).strip().zfill(10)
            records.append(
                ReferenceSecurityRecord(
                    source="sec:company_tickers_exchange",
                    source_record_key=f"{cik}:{symbol}:{exchange_code}",
                    symbol=symbol,
                    security_name=str(row["name"]).strip(),
                    exchange_code=exchange_code,
                    mic=MIC_BY_EXCHANGE.get(exchange_code),
                    asset_type="equity",
                    is_active=True,
                    is_test_issue=False,
                    is_etf=False,
                    cik=cik,
                    metadata={"exchange": exchange},
                )
            )
        return records


def reconcile_reference_records(
    session: Session,
    records: list[ReferenceSecurityRecord],
    *,
    retrieved_at: datetime | None = None,
    mark_missing_inactive: bool = True,
) -> dict[str, int]:
    now = retrieved_at or utc_now()
    inserted_assets = inserted_listings = updated_listings = excluded = enriched = 0
    seen_by_source: dict[str, set[str]] = {}
    for record in records:
        seen_by_source.setdefault(record.source, set()).add(record.source_record_key)
        outcome = eligibility(record)
        if outcome[0] == "EXCLUDED":
            excluded += 1
        listing = session.scalar(
            select(AssetListing).where(
                AssetListing.source == record.source,
                AssetListing.source_record_key == record.source_record_key,
                AssetListing.valid_to.is_(None),
            )
        )
        if listing is None:
            listing = session.scalar(
                select(AssetListing).where(
                    AssetListing.normalized_symbol == record.symbol,
                    AssetListing.exchange_code == record.exchange_code,
                    AssetListing.valid_to.is_(None),
                )
            )
        asset = session.get(Asset, listing.asset_id) if listing else None
        if asset is None:
            asset = session.scalar(select(Asset).where(Asset.symbol == record.symbol))
        if asset is None:
            asset = Asset(
                id=uuid.uuid5(
                    REFERENCE_NAMESPACE, f"security:{record.exchange_code}:{record.symbol}"
                ),
                symbol=record.symbol,
                name=record.security_name,
                asset_type=record.asset_type,
                exchange=record.exchange_code,
                currency="USD",
                is_active=record.is_active,
            )
            session.add(asset)
            session.flush()
            inserted_assets += 1
        issuer: Issuer | None = None
        if record.cik:
            issuer = session.scalar(select(Issuer).where(Issuer.cik == record.cik))
            if issuer is None:
                issuer = Issuer(
                    id=uuid.uuid5(REFERENCE_NAMESPACE, f"issuer:cik:{record.cik}"),
                    canonical_name=record.security_name,
                    search_name=record.security_name.casefold(),
                    cik=record.cik,
                    country="US",
                    provenance={"source": record.source},
                )
                session.add(issuer)
                session.flush()
            enriched += 1
        if listing is None:
            listing = AssetListing(
                asset_id=asset.id,
                issuer_id=issuer.id if issuer else None,
                symbol=record.symbol,
                normalized_symbol=record.symbol,
                security_name=record.security_name,
                exchange_code=record.exchange_code,
                mic=record.mic,
                asset_type=record.asset_type,
                listing_status="ACTIVE",
                is_active=record.is_active,
                is_test_issue=record.is_test_issue,
                is_etf=record.is_etf,
                eligibility_status=outcome[0],
                exclusion_reason=outcome[1],
                valid_from=now,
                source=record.source,
                source_record_key=record.source_record_key,
                provenance={"checksum": record.checksum},
            )
            session.add(listing)
            session.flush()
            inserted_listings += 1
        else:
            listing.issuer_id = issuer.id if issuer else listing.issuer_id
            listing.security_name = record.security_name
            listing.mic = record.mic
            listing.asset_type = record.asset_type
            listing.is_test_issue = record.is_test_issue
            listing.is_etf = record.is_etf
            listing.eligibility_status, listing.exclusion_reason = outcome
            listing.is_active = record.is_active
            listing.listing_status = "ACTIVE" if record.is_active else "INACTIVE"
            listing.provenance = {"checksum": record.checksum}
            updated_listings += 1
        asset.name = record.security_name
        asset.asset_type = record.asset_type
        asset.exchange = record.exchange_code
        asset.is_active = record.is_active
        if issuer and record.cik:
            existing_identifier = session.scalar(
                select(AssetIdentifier).where(
                    AssetIdentifier.asset_id == asset.id,
                    AssetIdentifier.identifier_type == "CIK",
                    AssetIdentifier.identifier_value == record.cik,
                    AssetIdentifier.valid_to.is_(None),
                )
            )
            if existing_identifier is None:
                session.add(
                    AssetIdentifier(
                        asset_id=asset.id,
                        issuer_id=issuer.id,
                        identifier_type="CIK",
                        identifier_value=record.cik,
                        source=record.source,
                        valid_from=now,
                        provenance={"checksum": record.checksum},
                    )
                )
        observation = session.scalar(
            select(ReferenceObservation).where(
                ReferenceObservation.source == record.source,
                ReferenceObservation.checksum == record.checksum,
            )
        )
        if observation is None:
            session.add(
                ReferenceObservation(
                    source=record.source,
                    source_record_key=record.source_record_key,
                    retrieval_time=now,
                    source_version=None,
                    checksum=record.checksum,
                    raw_object_reference=None,
                    media_type=(
                        "application/json" if record.source.startswith("sec:") else "text/plain"
                    ),
                    reconciliation_outcome="EXCLUDED" if outcome[0] == "EXCLUDED" else "MATCHED",
                    asset_id=asset.id,
                    issuer_id=issuer.id if issuer else None,
                    payload=record.metadata,
                )
            )
        capability = session.scalar(
            select(AssetCapability).where(
                AssetCapability.asset_id == asset.id,
                AssetCapability.capability == "REFERENCE",
                AssetCapability.provider_code == record.source,
            )
        )
        if capability is None:
            session.add(
                AssetCapability(
                    asset_id=asset.id,
                    capability="REFERENCE",
                    status="REFERENCE_AVAILABLE" if outcome[0] == "ELIGIBLE" else "INACTIVE",
                    provider_code=record.source,
                    feed_type="REFERENCE",
                    as_of_time=now,
                    reason=outcome[1],
                    details={"checksum": record.checksum},
                )
            )
        else:
            capability.status = "REFERENCE_AVAILABLE" if outcome[0] == "ELIGIBLE" else "INACTIVE"
            capability.as_of_time = now
            capability.reason = outcome[1]
            capability.details = {"checksum": record.checksum}

    inactive = 0
    if mark_missing_inactive:
        for source, keys in seen_by_source.items():
            current = session.scalars(
                select(AssetListing).where(
                    AssetListing.source == source,
                    AssetListing.valid_to.is_(None),
                    AssetListing.is_active.is_(True),
                )
            )
            for listing in current:
                if listing.source_record_key not in keys:
                    listing.is_active = False
                    listing.listing_status = "DELISTED"
                    listing.valid_to = now
                    inactive += 1
    session.flush()
    return {
        "records": len(records),
        "assets_inserted": inserted_assets,
        "listings_inserted": inserted_listings,
        "listings_updated": updated_listings,
        "listings_inactivated": inactive,
        "excluded": excluded,
        "sec_enriched": enriched,
    }
