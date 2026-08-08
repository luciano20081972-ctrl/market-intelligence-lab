from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from packages.world_data.manifests import sha256_bytes
from packages.world_data.temporal import QualityFlag, TemporalTruth


def normalize_cik(value: str | int) -> str:
    digits = str(value).strip().removeprefix("CIK").replace("-", "")
    if not digits.isdigit() or len(digits) > 10:
        raise ValueError("CIK must contain at most ten digits")
    return digits.zfill(10)


def normalize_accession(value: str) -> str:
    digits = value.replace("-", "").strip()
    if len(digits) != 18 or not digits.isdigit():
        raise ValueError("accession number must contain exactly eighteen digits")
    return f"{digits[:10]}-{digits[10:12]}-{digits[12:]}"


@dataclass(frozen=True)
class AcquiredPayload:
    body: bytes
    checksum: str
    retrieved_at: datetime
    source_url: str


class OfficialJsonClient:
    def __init__(self, user_agent: str, timeout: float = 20.0) -> None:
        self.user_agent = user_agent
        self.timeout = timeout

    def get(self, url: str, params: dict[str, str] | None = None) -> AcquiredPayload:
        with httpx.Client(timeout=self.timeout, headers={"User-Agent": self.user_agent}) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
        body = response.content
        return AcquiredPayload(body, sha256_bytes(body), datetime.now(UTC), str(response.url))


class SecDirectAdapter:
    base_url = "https://data.sec.gov"

    def __init__(self, client: OfficialJsonClient) -> None:
        self.client = client

    def submissions(self, cik: str | int) -> AcquiredPayload:
        return self.client.get(f"{self.base_url}/submissions/CIK{normalize_cik(cik)}.json")

    def companyfacts(self, cik: str | int) -> AcquiredPayload:
        cik_value = normalize_cik(cik)
        return self.client.get(f"{self.base_url}/api/xbrl/companyfacts/CIK{cik_value}.json")

    @staticmethod
    def parse_submissions(payload: bytes, retrieved_at: datetime) -> list[dict[str, Any]]:
        source = json.loads(payload)
        recent = source.get("filings", {}).get("recent", {})
        rows: list[dict[str, Any]] = []
        for index, accession in enumerate(recent.get("accessionNumber", [])):
            form = recent["form"][index]
            accepted_text = recent["acceptanceDateTime"][index].replace("Z", "+00:00")
            accepted = datetime.fromisoformat(accepted_text)
            rows.append({
                "cik": normalize_cik(source["cik"]),
                "accession_number": normalize_accession(accession),
                "form": form,
                "is_amendment": form.endswith("/A"),
                "filed": recent["filingDate"][index],
                "accepted_at": accepted,
                "retrieval_time": retrieved_at,
                "simulation_eligible_time": max(accepted, retrieved_at),
            })
        return rows


def parse_decimal(value: str) -> tuple[Decimal | None, tuple[QualityFlag, ...]]:
    if value in {".", "", "NA", "null"}:
        return None, (QualityFlag.MISSING,)
    try:
        return Decimal(value), ()
    except InvalidOperation:
        return None, (QualityFlag.MALFORMED,)


def parse_fred_observations(
    payload: bytes, retrieved_at: datetime, vintage: bool
) -> list[dict[str, Any]]:
    source = json.loads(payload)
    parsed: list[dict[str, Any]] = []
    for row in source.get("observations", []):
        observation = datetime.combine(date.fromisoformat(row["date"]), datetime.min.time(), UTC)
        revision = datetime.combine(
            date.fromisoformat(row.get("realtime_start", row["date"])), datetime.min.time(), UTC
        )
        value, flags = parse_decimal(str(row.get("value", ".")))
        publication = revision if vintage else retrieved_at
        truth = TemporalTruth(
            event_time=observation,
            observation_time=observation,
            publication_time=publication,
            retrieval_time=retrieved_at,
            effective_time=observation,
            revision_time=revision,
            simulation_eligible_time=max(publication, retrieved_at, revision),
            precision="day",
            quality_flags=flags + ((QualityFlag.REVISED,) if vintage else ()),
        )
        parsed.append({"value": value, "source_value": str(row.get("value", ".")), "truth": truth,
                       "realtime_end": row.get("realtime_end")})
    return parsed


def get_observation_as_of(rows: list[dict[str, Any]], as_of: datetime) -> dict[str, Any] | None:
    visible = [row for row in rows if row["truth"].visible_as_of(as_of)]
    return max(visible, key=lambda row: row["truth"].revision_time, default=None)


def parse_eia_electricity(payload: bytes, retrieved_at: datetime) -> list[dict[str, Any]]:
    source = json.loads(payload)
    rows: list[dict[str, Any]] = []
    for row in source.get("response", {}).get("data", []):
        period = str(row["period"])
        observed = datetime(int(period[:4]), int(period[5:7]), 1, tzinfo=UTC)
        value, flags = parse_decimal(str(row.get("price", row.get("value", ""))))
        truth = TemporalTruth(
            event_time=observed, observation_time=observed, publication_time=retrieved_at,
            retrieval_time=retrieved_at, effective_time=observed, revision_time=retrieved_at,
            simulation_eligible_time=retrieved_at, precision="month", quality_flags=flags,
        )
        rows.append({
            "value": value,
            "source_value": str(row.get("price", "")),
            "geography": row.get("stateid", "US"),
            "units": row.get("price-units", "cents/kWh"),
            "truth": truth,
        })
    return rows
