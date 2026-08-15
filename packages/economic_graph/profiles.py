from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from packages.database.models import (
    CompanyDriverEntry,
    CompanyDriverProfile,
    DataRelevanceDecision,
    EconomicEntity,
    EconomicRelationship,
    GraphRecomputeJob,
)

PRIOR_VERSION = "driver-priors-v1"
ROUTER_VERSION = "data-relevance-router-v1"


@dataclass(frozen=True)
class DriverPrior:
    relevance: Decimal
    reason: str


@dataclass(frozen=True)
class DatasetDomain:
    dataset_id: str
    label: str
    availability: str
    domains: dict[str, Decimal]


@lru_cache
def load_driver_priors(path: Path | None = None) -> dict[str, dict[str, DriverPrior]]:
    config_path = path or Path(__file__).parents[2] / "config" / "driver-priors.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    profiles: dict[str, dict[str, DriverPrior]] = {}
    for key, profile in payload["profiles"].items():
        profiles[key] = {
            category: DriverPrior(Decimal(str(item["relevance"])), str(item["reason"]))
            for category, item in profile["drivers"].items()
        }
    return profiles


@lru_cache
def load_dataset_domains(path: Path | None = None) -> tuple[DatasetDomain, ...]:
    config_path = path or Path(__file__).parents[2] / "config" / "dataset-domains.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return tuple(
        DatasetDomain(
            dataset_id=dataset_id,
            label=str(item["label"]),
            availability=str(item["availability"]),
            domains={key: Decimal(str(value)) for key, value in item["domains"].items()},
        )
        for dataset_id, item in sorted(payload["datasets"].items())
    )


def _sector_key(value: str) -> str:
    normalized = value.casefold().replace(" ", "_")
    alias_map = {
        "semiconductors": "semiconductor",
        "airlines": "airline",
        "air_transportation": "airline",
        "agricultural_products": "agriculture",
        "crop_production": "agriculture",
    }
    return alias_map.get(normalized, normalized)


def _relationship_categories(relationship: EconomicRelationship, other: EconomicEntity) -> set[str]:
    categories: set[str] = set()
    predicate = relationship.predicate
    name = other.canonical_name.casefold()
    if predicate == "USES_TECHNOLOGY" or other.entity_type == "Technology":
        categories.add("technology")
    if predicate in {"SUPPLIES", "BUYS_FROM", "SELLS_TO", "SHIPS_THROUGH"}:
        categories.add("supply_chain")
    if predicate == "REGULATED_BY" or other.entity_type in {"Regulation", "GovernmentAgency"}:
        categories.add("regulatory")
    if predicate in {"HAS_SEGMENT", "PRODUCES", "USES"}:
        categories.add("industry")
    if other.entity_type in {"Country", "Region", "Port"}:
        categories.update({"geopolitical", "geospatial"})
    if other.entity_type in {"EnergyMarket", "Commodity"}:
        category = (
            "energy"
            if any(term in name for term in ("fuel", "energy", "electric"))
            else "commodity"
        )
        categories.add(category)
    if "water" in name or "drought" in name:
        categories.add("water")
    if any(term in name for term in ("weather", "drought", "climate", "storm")):
        categories.add("weather_environmental")
    if other.entity_type == "TransportationNode" or predicate == "SHIPS_THROUGH":
        categories.add("transportation")
    if any(term in name for term in ("crop", "soil", "fertilizer", "agriculture")):
        categories.add("agriculture")
    return categories


def generate_driver_profile(
    session: Session,
    *,
    company: EconomicEntity,
    sector: str,
    trigger_reason: str,
    user_overrides: dict[str, Decimal] | None = None,
    generated_at: datetime | None = None,
) -> CompanyDriverProfile:
    if company.entity_type != "Company":
        raise ValueError("driver profiles require a Company entity")
    now = generated_at or datetime.now(UTC)
    priors = load_driver_priors()
    selected = dict(priors["default"])
    selected.update(priors.get(_sector_key(sector), {}))
    overrides = user_overrides or {}
    for category, value in overrides.items():
        if value < 0 or value > 1:
            raise ValueError(f"driver override {category} must be between 0 and 1")
    relationships = session.scalars(
        select(EconomicRelationship).where(
            EconomicRelationship.workspace_id == company.workspace_id,
            or_(
                EconomicRelationship.subject_entity_id == company.id,
                EconomicRelationship.object_entity_id == company.id,
            ),
            EconomicRelationship.status.in_(("verified", "disputed")),
            EconomicRelationship.simulation_eligible_time <= now,
            EconomicRelationship.valid_from <= now,
            or_(EconomicRelationship.valid_to.is_(None), EconomicRelationship.valid_to > now),
        )
    ).all()
    evidence: dict[str, list[tuple[EconomicRelationship, EconomicEntity]]] = {}
    for relationship in relationships:
        other_id = (
            relationship.object_entity_id
            if relationship.subject_entity_id == company.id
            else relationship.subject_entity_id
        )
        other = session.get(EconomicEntity, other_id)
        if other is None or other.simulation_eligible_time > now:
            continue
        for category in _relationship_categories(relationship, other):
            evidence.setdefault(category, []).append((relationship, other))
    categories = sorted(set(selected) | set(evidence) | set(overrides))
    latest_version = session.scalar(
        select(func.max(CompanyDriverProfile.version)).where(
            CompanyDriverProfile.workspace_id == company.workspace_id,
            CompanyDriverProfile.company_entity_id == company.id,
        )
    )
    profile = CompanyDriverProfile(
        workspace_id=company.workspace_id,
        company_entity_id=company.id,
        prior_version=PRIOR_VERSION,
        generated_at=now,
        version=int(latest_version or 0) + 1,
        simulation_eligible_time=max(
            [company.simulation_eligible_time]
            + [relationship.simulation_eligible_time for relationship in relationships]
        ),
        trigger_reason=trigger_reason,
    )
    session.add(profile)
    session.flush()
    for category in categories:
        prior = selected.get(category)
        prior_score = prior.relevance if prior else Decimal("0")
        links = evidence.get(category, [])
        evidence_score = max(
            (relationship.confidence for relationship, _ in links),
            default=Decimal("0"),
        )
        override = overrides.get(category)
        effective = override if override is not None else max(prior_score, evidence_score)
        confidence = max(
            Decimal("0.50") if prior_score > 0 else Decimal("0"),
            evidence_score,
            Decimal("0.90") if override is not None else Decimal("0"),
        )
        reasons = []
        if prior:
            reasons.append(prior.reason)
        if links:
            reasons.append(f"{len(links)} active evidence-backed graph relationship(s)")
        if override is not None:
            reasons.append("workspace user override")
        session.add(
            CompanyDriverEntry(
                workspace_id=company.workspace_id,
                profile_id=profile.id,
                driver_category=category,
                linked_entity_ids=sorted({str(other.id) for _, other in links}),
                supporting_relationship_ids=sorted(
                    {str(relationship.id) for relationship, _ in links}
                ),
                prior_relevance=prior_score,
                evidence_relevance=evidence_score,
                historical_evidence_relevance=None,
                user_override=override,
                effective_relevance=effective,
                confidence=confidence,
                explanation="; ".join(reasons) or "No active support",
            )
        )
    session.flush()
    return profile


def route_datasets(
    session: Session,
    profile: CompanyDriverProfile,
    *,
    dataset_overrides: dict[str, str] | None = None,
) -> list[DataRelevanceDecision]:
    entries = session.scalars(
        select(CompanyDriverEntry).where(CompanyDriverEntry.profile_id == profile.id)
    ).all()
    by_category = {entry.driver_category: entry for entry in entries}
    overrides = dataset_overrides or {}
    decisions: list[DataRelevanceDecision] = []
    for dataset in load_dataset_domains():
        existing = session.scalar(
            select(DataRelevanceDecision).where(
                DataRelevanceDecision.profile_id == profile.id,
                DataRelevanceDecision.dataset_id == dataset.dataset_id,
                DataRelevanceDecision.router_version == ROUTER_VERSION,
            )
        )
        if existing is not None:
            decisions.append(existing)
            continue
        scored = [
            (entry.effective_relevance * weight, category, entry)
            for category, weight in dataset.domains.items()
            if (entry := by_category.get(category)) is not None
        ]
        score, category, entry = max(
            scored,
            default=(Decimal("0"), "none", None),
            key=lambda item: (item[0], item[1]),
        )
        if dataset.dataset_id in overrides:
            decision = overrides[dataset.dataset_id]
            if decision not in {"PROCESS", "DEFER", "IGNORE", "REVIEW"}:
                raise ValueError("dataset override must be PROCESS, DEFER, IGNORE, or REVIEW")
            reasons = ["manual_override"]
        elif score >= Decimal("0.65"):
            decision = "PROCESS"
            reasons = ["high_driver_relevance", f"driver:{category}"]
        elif score >= Decimal("0.35"):
            decision = "DEFER"
            reasons = ["moderate_driver_relevance", f"driver:{category}"]
        elif score < Decimal("0.15"):
            decision = "IGNORE"
            reasons = ["no_relevant_driver"]
        else:
            decision = "REVIEW"
            reasons = ["uncertain_driver_relevance", f"driver:{category}"]
        if dataset.availability != "implemented":
            reasons.append(f"availability:{dataset.availability}")
        paths: list[dict[str, Any]] = []
        if entry is not None:
            paths = [
                {
                    "company_entity_id": str(profile.company_entity_id),
                    "relationship_id": relationship_id,
                    "linked_entity_id": linked_id,
                    "driver_category": category,
                }
                for relationship_id, linked_id in zip(
                    entry.supporting_relationship_ids,
                    entry.linked_entity_ids,
                    strict=False,
                )
            ]
        item = DataRelevanceDecision(
            workspace_id=profile.workspace_id,
            profile_id=profile.id,
            company_entity_id=profile.company_entity_id,
            dataset_id=dataset.dataset_id,
            decision=decision,
            relevance_score=min(score, Decimal("1")),
            reason_codes=reasons,
            supporting_graph_paths=paths,
            confidence=entry.confidence if entry is not None else Decimal("0.25"),
            router_version=ROUTER_VERSION,
        )
        session.add(item)
        decisions.append(item)
    session.flush()
    return sorted(
        decisions,
        key=lambda item: (item.decision, -item.relevance_score, item.dataset_id),
    )


def process_recompute_job(
    session: Session,
    job: GraphRecomputeJob,
    *,
    sector: str,
    user_overrides: dict[str, Decimal] | None = None,
) -> CompanyDriverProfile:
    if job.status not in {"queued", "failed"}:
        raise ValueError("graph recompute job is not runnable")
    company = session.get(EconomicEntity, job.company_entity_id)
    if company is None:
        raise LookupError("graph recompute company does not exist")
    job.status = "running"
    job.started_at = datetime.now(UTC)
    try:
        profile = generate_driver_profile(
            session,
            company=company,
            sector=sector,
            trigger_reason=job.trigger_reason,
            user_overrides=user_overrides,
        )
        route_datasets(session, profile)
    except Exception as exc:
        job.status = "failed"
        job.error_message = type(exc).__name__
        job.completed_at = datetime.now(UTC)
        raise
    job.status = "succeeded"
    job.completed_at = datetime.now(UTC)
    session.flush()
    return profile
