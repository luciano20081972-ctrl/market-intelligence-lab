from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db, get_principal, get_workspace_context
from packages.auth import AuthPrincipal
from packages.core.time import utc_now
from packages.database.models import (
    SecCompany,
    SecDocument,
    SecFact,
    SecFiling,
    SecIngestionJob,
    SecInsiderTransaction,
    SecInstitutionalHolding,
    SecParseResult,
)
from packages.provenance import record_audit_event
from packages.sec_intelligence import SUPPORTED_FORMS, FixtureSecAdapter
from packages.sec_intelligence.adapters import normalize_cik
from packages.security import WorkspaceContext

router = APIRouter(prefix="/sec", tags=["SEC intelligence"])


class SecImportRequest(BaseModel):
    cik: str = Field(min_length=1, max_length=16)
    forms: list[str] = Field(default_factory=lambda: ["10-K", "4", "13F-HR"], max_length=7)
    mode: str = Field(default="fixture", pattern="^fixture$")
    idempotency_key: str = Field(min_length=8, max_length=120)

    @field_validator("forms")
    @classmethod
    def validate_forms(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip().upper() for item in value))
        if set(normalized) - SUPPORTED_FORMS:
            raise ValueError("One or more SEC forms are unsupported")
        return normalized


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _company_response(value: SecCompany) -> dict[str, object]:
    return {
        "id": value.id,
        "cik": value.cik,
        "name": value.name,
        "tickers": value.tickers,
        "sic": value.sic,
        "submissions_url": value.submissions_url,
        "facts_url": value.facts_url,
        "retrieved_at": value.retrieved_at,
        "source_checksum": value.source_checksum,
    }


def _filing_response(value: SecFiling, company: SecCompany | None = None) -> dict[str, object]:
    return {
        "id": value.id,
        "company_id": value.company_id,
        "company_name": company.name if company else None,
        "cik": company.cik if company else None,
        "accession_number": value.accession_number,
        "form_type": value.form_type,
        "filing_date": value.filing_date,
        "accepted_at": value.accepted_at,
        "reporting_period": value.reporting_period,
        "source_url": value.source_url,
        "retrieved_at": value.retrieved_at,
        "content_checksum": value.content_checksum,
        "raw_document_reference": value.raw_document_reference,
        "parser_version": value.parser_version,
        "edgartools_version": value.edgartools_version,
        "is_amendment": value.is_amendment,
        "simulation_eligible_at": value.simulation_eligible_at,
    }


def _job_response(value: SecIngestionJob) -> dict[str, object]:
    return {
        "id": value.id,
        "cik": value.cik,
        "forms": value.forms,
        "mode": value.mode,
        "status": value.status,
        "records_processed": value.records_processed,
        "error_message": value.error_message,
        "requested_at": value.requested_at,
        "completed_at": value.completed_at,
    }


@router.get("/companies")
def list_companies(
    session: Session = Depends(get_db),
    query: str | None = Query(default=None, max_length=120),
) -> dict[str, object]:
    statement = select(SecCompany).order_by(SecCompany.name)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            (SecCompany.name.ilike(pattern)) | (SecCompany.cik.ilike(pattern))
        )
    values = session.scalars(statement.limit(100)).all()
    return {"items": [_company_response(value) for value in values], "total": len(values)}


@router.get("/companies/{cik}")
def get_company(cik: str, session: Session = Depends(get_db)) -> dict[str, object]:
    value = session.scalar(select(SecCompany).where(SecCompany.cik == normalize_cik(cik)))
    if value is None:
        raise HTTPException(status_code=404, detail="SEC company was not found")
    return _company_response(value)


@router.get("/filings")
def list_filings(
    session: Session = Depends(get_db),
    cik: str | None = None,
    form_type: str | None = None,
) -> dict[str, object]:
    statement = (
        select(SecFiling, SecCompany)
        .join(SecCompany, SecCompany.id == SecFiling.company_id)
        .order_by(SecFiling.accepted_at.desc())
    )
    if cik:
        statement = statement.where(SecCompany.cik == normalize_cik(cik))
    if form_type:
        statement = statement.where(SecFiling.form_type == form_type.upper())
    rows = session.execute(statement.limit(200)).all()
    return {
        "items": [_filing_response(filing, company) for filing, company in rows],
        "total": len(rows),
    }


@router.get("/filings/{filing_id}")
def get_filing(filing_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    filing = session.get(SecFiling, filing_id)
    if filing is None:
        raise HTTPException(status_code=404, detail="SEC filing was not found")
    company = session.get(SecCompany, filing.company_id)
    response = _filing_response(filing, company)
    response["documents"] = [
        {
            "id": value.id,
            "sequence": value.sequence,
            "document_type": value.document_type,
            "source_url": value.source_url,
            "content_reference": value.content_reference,
            "content_checksum": value.content_checksum,
        }
        for value in session.scalars(
            select(SecDocument)
            .where(SecDocument.filing_id == filing.id)
            .order_by(SecDocument.sequence)
        ).all()
    ]
    response["facts"] = [
        {
            "taxonomy": value.taxonomy,
            "concept": value.concept,
            "unit": value.unit,
            "numeric_value": value.numeric_value,
            "text_value": value.text_value,
            "period_start": value.period_start,
            "period_end": value.period_end,
            "filed_at": value.filed_at,
        }
        for value in session.scalars(
            select(SecFact).where(SecFact.filing_id == filing.id).order_by(SecFact.concept)
        ).all()
    ]
    return response


@router.get("/insider-transactions")
def insider_transactions(session: Session = Depends(get_db)) -> dict[str, object]:
    values = session.scalars(
        select(SecInsiderTransaction).order_by(SecInsiderTransaction.transaction_date.desc())
    ).all()
    return {
        "items": [
            {
                "id": value.id,
                "company_id": value.company_id,
                "filing_id": value.filing_id,
                "owner_name": value.owner_name,
                "relationship": value.relationship,
                "transaction_code": value.transaction_code,
                "security_title": value.security_title,
                "transaction_date": value.transaction_date,
                "shares": value.shares,
                "price": value.price,
                "acquired_disposed": value.acquired_disposed,
            }
            for value in values
        ],
        "total": len(values),
    }


@router.get("/institutional-holdings")
def institutional_holdings(session: Session = Depends(get_db)) -> dict[str, object]:
    values = session.scalars(
        select(SecInstitutionalHolding).order_by(SecInstitutionalHolding.value_usd.desc())
    ).all()
    return {
        "items": [
            {
                "id": value.id,
                "filing_id": value.filing_id,
                "company_id": value.company_id,
                "issuer_name": value.issuer_name,
                "cusip": value.cusip,
                "as_of_date": value.as_of_date,
                "shares": value.shares,
                "value_usd": value.value_usd,
                "voting_authority": value.voting_authority,
            }
            for value in values
        ],
        "total": len(values),
    }


@router.post("/imports", status_code=status.HTTP_201_CREATED)
def create_import(
    payload: SecImportRequest,
    context: WorkspaceContext = Depends(get_workspace_context),
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    existing = session.scalar(
        select(SecIngestionJob).where(
            SecIngestionJob.workspace_id == context.workspace_id,
            SecIngestionJob.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        return _job_response(existing)
    job = SecIngestionJob(
        workspace_id=context.workspace_id,
        requested_by_user_id=principal.user_id,
        cik=normalize_cik(payload.cik),
        forms=payload.forms,
        mode=payload.mode,
        status="running",
        idempotency_key=payload.idempotency_key,
        configuration={"network_access": False, "provider": "fixture"},
    )
    session.add(job)
    session.flush()
    try:
        imported = FixtureSecAdapter().import_company(job.cik, tuple(payload.forms))
        company_data = imported["company"]
        company = session.scalar(select(SecCompany).where(SecCompany.cik == company_data["cik"]))
        if company is None:
            company = SecCompany(
                cik=company_data["cik"],
                name=company_data["name"],
                tickers=company_data["tickers"],
                sic=company_data["sic"],
                submissions_url=company_data["submissions_url"],
                facts_url=company_data["facts_url"],
                retrieved_at=_parse_datetime(imported["retrieved_at"]),
                source_checksum=imported["checksum"],
            )
            session.add(company)
            session.flush()
        filings: dict[str, SecFiling] = {}
        for value in imported["filings"]:
            filing = session.scalar(
                select(SecFiling).where(SecFiling.accession_number == value["accession_number"])
            )
            if filing is None:
                checksum = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
                filing = SecFiling(
                    company_id=company.id,
                    accession_number=value["accession_number"],
                    form_type=value["form_type"],
                    filing_date=date.fromisoformat(value["filing_date"]),
                    accepted_at=_parse_datetime(value["accepted_at"]),
                    reporting_period=date.fromisoformat(value["reporting_period"]),
                    source_url=value["source_url"],
                    retrieved_at=_parse_datetime(imported["retrieved_at"]),
                    content_checksum=checksum,
                    raw_document_reference=value["raw_document_reference"],
                    parser_version=imported["parser_version"],
                    edgartools_version=imported["edgartools_version"],
                    is_amendment=value["is_amendment"],
                    simulation_eligible_at=_parse_datetime(value["accepted_at"]),
                )
                session.add(filing)
                session.flush()
                session.add(
                    SecDocument(
                        filing_id=filing.id,
                        sequence=1,
                        document_type=value["form_type"],
                        source_url=value["source_url"],
                        content_reference=value["raw_document_reference"],
                        content_checksum=checksum,
                    )
                )
                session.add(
                    SecParseResult(
                        ingestion_job_id=job.id,
                        filing_id=filing.id,
                        status="parsed",
                        parser_version=imported["parser_version"],
                        parser_checksum=checksum,
                        warnings=[],
                    )
                )
            filings[value["accession_number"]] = filing
        for value in imported["facts"]:
            filing = filings[value["accession_number"]]
            exists = session.scalar(
                select(func.count(SecFact.id)).where(
                    SecFact.filing_id == filing.id,
                    SecFact.concept == value["concept"],
                    SecFact.period_end == date.fromisoformat(value["period_end"]),
                )
            )
            if not exists:
                session.add(
                    SecFact(
                        company_id=company.id,
                        filing_id=filing.id,
                        taxonomy=value["taxonomy"],
                        concept=value["concept"],
                        unit=value["unit"],
                        numeric_value=Decimal(value["numeric_value"]),
                        text_value=None,
                        period_start=date.fromisoformat(value["period_start"]),
                        period_end=date.fromisoformat(value["period_end"]),
                        filed_at=_parse_datetime(value["filed_at"]),
                    )
                )
        for value in imported["insider_transactions"]:
            filing = filings[value["accession_number"]]
            exists = session.scalar(
                select(func.count(SecInsiderTransaction.id)).where(
                    SecInsiderTransaction.filing_id == filing.id,
                    SecInsiderTransaction.owner_name == value["owner_name"],
                )
            )
            if not exists:
                session.add(
                    SecInsiderTransaction(
                        company_id=company.id,
                        filing_id=filing.id,
                        owner_name=value["owner_name"],
                        relationship=value["relationship"],
                        transaction_code=value["transaction_code"],
                        security_title=value["security_title"],
                        transaction_date=date.fromisoformat(value["transaction_date"]),
                        shares=Decimal(value["shares"]),
                        price=Decimal(value["price"]) if value["price"] is not None else None,
                        acquired_disposed=value["acquired_disposed"],
                    )
                )
        for value in imported["institutional_holdings"]:
            filing = filings[value["accession_number"]]
            exists = session.scalar(
                select(func.count(SecInstitutionalHolding.id)).where(
                    SecInstitutionalHolding.filing_id == filing.id,
                    SecInstitutionalHolding.cusip == value["cusip"],
                )
            )
            if not exists:
                session.add(
                    SecInstitutionalHolding(
                        filing_id=filing.id,
                        company_id=None,
                        issuer_name=value["issuer_name"],
                        cusip=value["cusip"],
                        as_of_date=date.fromisoformat(value["as_of_date"]),
                        shares=Decimal(value["shares"]),
                        value_usd=Decimal(value["value_usd"]),
                        voting_authority=value["voting_authority"],
                    )
                )
        job.status = "completed"
        job.records_processed = len(imported["filings"])
        job.completed_at = utc_now()
        record_audit_event(
            session,
            action="sec.import.completed",
            entity_type="sec_ingestion_job",
            entity_id=job.id,
            details={"cik": job.cik, "forms": job.forms, "network_access": False},
        )
        session.commit()
    except (ValueError, KeyError, TypeError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _job_response(job)


@router.get("/imports/{job_id}")
def get_import(job_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    value = session.get(SecIngestionJob, job_id)
    if value is None:
        raise HTTPException(status_code=404, detail="SEC import was not found")
    return _job_response(value)
