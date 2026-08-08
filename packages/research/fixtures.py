from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import (
    EconomicEntity,
    FeatureDefinition,
    FeatureDefinitionVersion,
    FeatureSet,
    FeatureSetMembership,
    ResearchBudget,
    ResearchResolutionPolicy,
    ResearchUniverse,
    ResearchUniverseMembership,
    ResearchUniverseVersion,
)
from packages.research.service import create_feature_value, run_screening

REFERENCE_AS_OF = datetime(2026, 2, 1, 12, tzinfo=UTC)
POLICY_VERSION = "progressive-resolution-v1"

FEATURE_LIBRARY: tuple[dict[str, Any], ...] = (
    {
        "key": "revenue_growth_yoy",
        "domain": "fundamental",
        "unit": "ratio",
        "datasets": ["sec.companyfacts"],
    },
    {
        "key": "operating_margin",
        "domain": "fundamental",
        "unit": "ratio",
        "datasets": ["sec.companyfacts"],
    },
    {
        "key": "cash_growth",
        "domain": "fundamental",
        "unit": "ratio",
        "datasets": ["sec.companyfacts"],
    },
    {
        "key": "inflation_change",
        "domain": "macro",
        "unit": "ratio",
        "datasets": ["alfred.vintages"],
    },
    {
        "key": "unemployment_change",
        "domain": "macro",
        "unit": "ratio",
        "datasets": ["alfred.vintages"],
    },
    {
        "key": "yield_curve_proxy",
        "domain": "macro",
        "unit": "percentage_points",
        "datasets": ["alfred.vintages"],
    },
    {
        "key": "electricity_price_change_3m",
        "domain": "energy",
        "unit": "ratio",
        "datasets": ["eia.electricity.retail-price"],
    },
    {"key": "geographic_exposure_count", "domain": "geopolitical", "unit": "count", "datasets": []},
    {
        "key": "regulatory_relationship_count",
        "domain": "geopolitical",
        "unit": "count",
        "datasets": [],
    },
    {"key": "energy_exposure_confidence", "domain": "energy", "unit": "confidence", "datasets": []},
    {"key": "external_driver_change_count", "domain": "industry", "unit": "count", "datasets": []},
    {
        "key": "data_completeness_score",
        "domain": "research_quality",
        "unit": "score",
        "datasets": [],
    },
    {
        "key": "source_freshness_score",
        "domain": "research_quality",
        "unit": "score",
        "datasets": [],
    },
    {
        "key": "driver_evidence_strength",
        "domain": "research_quality",
        "unit": "confidence",
        "datasets": [],
    },
    {
        "key": "market_momentum_90d",
        "domain": "market",
        "unit": "ratio",
        "datasets": ["market.daily-prices"],
    },
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _truth_fields(index: int, archetype: str) -> dict[str, Any]:
    observed = REFERENCE_AS_OF - timedelta(days=10)
    published = REFERENCE_AS_OF - timedelta(days=5)
    return {
        "status": "verified",
        "valid_from": observed,
        "valid_to": None,
        "first_seen": published,
        "last_verified": REFERENCE_AS_OF,
        "event_time": observed,
        "observation_time": observed,
        "publication_time": published,
        "retrieval_time": REFERENCE_AS_OF - timedelta(days=1),
        "effective_time": observed,
        "revision_time": published,
        "simulation_eligible_time": REFERENCE_AS_OF - timedelta(days=1),
        "time_precision": "day",
        "source_time_zone": "UTC",
        "confidence": Decimal("0.90"),
        "provenance_json": {"fixture": "v0.9", "index": index, "archetype": archetype},
    }


def _companies(session: Session, workspace_id: uuid.UUID) -> list[EconomicEntity]:
    companies = list(
        session.scalars(
            select(EconomicEntity)
            .where(
                EconomicEntity.workspace_id == workspace_id,
                EconomicEntity.entity_type == "Company",
            )
            .order_by(EconomicEntity.canonical_name)
        )
    )
    if len(companies) >= 100 and all(
        "research_fixture_index" in (company.provenance_json or {}) for company in companies[:100]
    ):
        return sorted(
            companies[:100],
            key=lambda company: int(company.provenance_json["research_fixture_index"]),
        )
    archetypes = ("semiconductor", "airline", "agriculture")
    for index in range(len(companies), 100):
        archetype = archetypes[index % len(archetypes)]
        company = EconomicEntity(
            workspace_id=workspace_id,
            entity_type="Company",
            canonical_name=f"Reference Company {index + 1:03d}",
            normalized_name=f"reference company {index + 1:03d}",
            **_truth_fields(index, archetype),
        )
        session.add(company)
        companies.append(company)
    session.flush()
    for index, company in enumerate(companies[:100]):
        provenance = dict(company.provenance_json or {})
        provenance.setdefault("archetype", archetypes[index % len(archetypes)])
        provenance["research_fixture_index"] = index
        company.provenance_json = provenance
    return companies[:100]


def _universe(
    session: Session, workspace_id: uuid.UUID, companies: list[EconomicEntity]
) -> tuple[ResearchUniverse, ResearchUniverseVersion]:
    universe = session.scalar(
        select(ResearchUniverse).where(
            ResearchUniverse.workspace_id == workspace_id,
            ResearchUniverse.name == "Synthetic 100-Company Research Universe",
        )
    )
    if universe is None:
        universe = ResearchUniverse(
            workspace_id=workspace_id,
            name="Synthetic 100-Company Research Universe",
            description=(
                "Deterministic fixture; not a licensed live index or recommendation universe."
            ),
            owner_type="system",
            source="deterministic-v0.9-fixture",
            selection_rules={"count": 100, "asset_type": "synthetic_equity"},
        )
        session.add(universe)
        session.flush()
    version = session.scalar(
        select(ResearchUniverseVersion).where(
            ResearchUniverseVersion.universe_id == universe.id,
            ResearchUniverseVersion.version == 1,
        )
    )
    if version is None:
        member_ids = sorted(str(item.id) for item in companies)
        version = ResearchUniverseVersion(
            universe_id=universe.id,
            version=1,
            effective_from=REFERENCE_AS_OF - timedelta(days=365),
            effective_to=None,
            simulation_eligible_time=REFERENCE_AS_OF - timedelta(days=2),
            membership_checksum=_digest("|".join(member_ids)),
            provenance={"fixture": True, "count": 100},
        )
        session.add(version)
        session.flush()
        for company in companies:
            session.add(
                ResearchUniverseMembership(
                    universe_version_id=version.id,
                    entity_id=company.id,
                    valid_from=REFERENCE_AS_OF - timedelta(days=365),
                    valid_to=None,
                    simulation_eligible_time=REFERENCE_AS_OF - timedelta(days=2),
                    source_manifest_id=None,
                    provenance={"source": "deterministic-v0.9-fixture"},
                )
            )
    return universe, version


def _features(
    session: Session, workspace_id: uuid.UUID
) -> tuple[FeatureSet, list[tuple[FeatureDefinition, FeatureDefinitionVersion]]]:
    definitions: list[tuple[FeatureDefinition, FeatureDefinitionVersion]] = []
    for item in FEATURE_LIBRARY:
        definition = session.scalar(
            select(FeatureDefinition).where(
                FeatureDefinition.workspace_id == workspace_id,
                FeatureDefinition.feature_key == item["key"],
            )
        )
        if definition is None:
            definition = FeatureDefinition(
                workspace_id=workspace_id,
                feature_key=item["key"],
                name=item["key"].replace("_", " ").title(),
                description=f"Deterministic reference measurement for {item['key']}.",
                domain=item["domain"],
                entity_type="Company",
                status="active",
            )
            session.add(definition)
            session.flush()
        version = session.scalar(
            select(FeatureDefinitionVersion).where(
                FeatureDefinitionVersion.feature_definition_id == definition.id,
                FeatureDefinitionVersion.version == 1,
            )
        )
        if version is None:
            version = FeatureDefinitionVersion(
                feature_definition_id=definition.id,
                version=1,
                output_type="numeric",
                unit=item["unit"],
                frequency="monthly",
                lookback_requirement="90d",
                computation_method="deterministic-reference-formula",
                implementation_version="mil-feature-v1",
                required_datasets=item["datasets"],
                required_graph_drivers=[item["domain"]],
                temporal_policy={"visibility": "simulation_eligible_time <= as_of_time"},
                missing_data_policy="mark_missing",
                normalization_policy="point_in_time_percentile",
                cost_class="low" if item["datasets"] else "free",
                determinism="deterministic",
            )
            session.add(version)
            session.flush()
        definitions.append((definition, version))
    feature_set = session.scalar(
        select(FeatureSet).where(
            FeatureSet.workspace_id == workspace_id,
            FeatureSet.key == "cheap-screen-v1",
            FeatureSet.version == 1,
        )
    )
    if feature_set is None:
        feature_set = FeatureSet(
            workspace_id=workspace_id,
            key="cheap-screen-v1",
            name="Reference Cheap Screen",
            version=1,
            owner="system",
            intended_resolution="LEVEL_1",
            estimated_compute_cost="low",
            active_from=REFERENCE_AS_OF - timedelta(days=30),
            active_to=None,
        )
        session.add(feature_set)
        session.flush()
        for position, (_, version) in enumerate(definitions):
            session.add(
                FeatureSetMembership(
                    feature_set_id=feature_set.id,
                    feature_version_id=version.id,
                    position=position,
                )
            )
    return feature_set, definitions


def _policy(
    session: Session, workspace_id: uuid.UUID
) -> tuple[ResearchResolutionPolicy, dict[str, ResearchBudget]]:
    configuration: dict[str, Any] = {
        "levels": {
            "LEVEL_0": {"maximum_population": 100, "datasets": [], "refresh_days": 30},
            "LEVEL_1": {
                "maximum_population": 50,
                "datasets": ["cheap-screen-v1"],
                "refresh_days": 30,
            },
            "LEVEL_2": {
                "maximum_population": 20,
                "datasets": ["sec.companyfacts"],
                "refresh_days": 14,
            },
            "LEVEL_3": {
                "maximum_population": 8,
                "datasets": ["routed-domain-data"],
                "refresh_days": 7,
            },
            "LEVEL_4": {
                "maximum_population": 3,
                "datasets": [],
                "refresh_days": 7,
                "meaning": "future AI research candidate only",
            },
        }
    }
    checksum = _digest(str(configuration))
    policy = session.scalar(
        select(ResearchResolutionPolicy).where(
            ResearchResolutionPolicy.workspace_id == workspace_id,
            ResearchResolutionPolicy.version == POLICY_VERSION,
        )
    )
    if policy is None:
        policy = ResearchResolutionPolicy(
            workspace_id=workspace_id,
            version=POLICY_VERSION,
            configuration=configuration,
            checksum=checksum,
            active_from=REFERENCE_AS_OF - timedelta(days=30),
        )
        session.add(policy)
        session.flush()
    budgets: dict[str, ResearchBudget] = {}
    for level, item in configuration["levels"].items():
        maximum_population = int(item["maximum_population"])
        budget = session.scalar(
            select(ResearchBudget).where(
                ResearchBudget.workspace_id == workspace_id,
                ResearchBudget.policy_id == policy.id,
                ResearchBudget.level == level,
            )
        )
        if budget is None:
            budget = ResearchBudget(
                workspace_id=workspace_id,
                policy_id=policy.id,
                level=level,
                limits={
                    "maximum_companies": maximum_population,
                    "api_requests_per_company": 1 if level in {"LEVEL_2", "LEVEL_3"} else 0,
                    "download_bytes": maximum_population * 100_000,
                    "storage_bytes": maximum_population * 50_000,
                    "cpu_seconds": maximum_population * (int(level[-1]) + 1),
                    "ai_token_allowance": 0,
                    "maximum_concurrent_jobs": 4,
                },
                cost_class=("free", "low", "medium", "high", "premium")[int(level[-1])],
                monetary_estimate=None,
            )
            session.add(budget)
        budgets[level] = budget
    session.flush()
    return policy, budgets


def _materialize(
    session: Session,
    workspace_id: uuid.UUID,
    companies: list[EconomicEntity],
    definitions: list[tuple[FeatureDefinition, FeatureDefinitionVersion]],
) -> None:
    for company_index, company in enumerate(companies):
        archetype = company.provenance_json.get("archetype", "semiconductor")
        archetype_bias = {"semiconductor": 3, "airline": 2, "agriculture": 1}[archetype]
        for feature_index, (definition, version) in enumerate(definitions):
            raw = ((company_index * 17 + feature_index * 11 + archetype_bias * 7) % 101) / 100
            if definition.feature_key.endswith("_count"):
                value = Decimal(str(int(raw * 10)))
            else:
                value = Decimal(str(round(raw, 4)))
            manifest = {
                "company_index": company_index,
                "feature": definition.feature_key,
                "eligible": (REFERENCE_AS_OF - timedelta(days=1)).isoformat(),
            }
            create_feature_value(
                session,
                workspace_id=workspace_id,
                feature_version=version,
                entity_id=company.id,
                observation_time=REFERENCE_AS_OF - timedelta(days=10),
                effective_time=REFERENCE_AS_OF - timedelta(days=10),
                calculation_time=REFERENCE_AS_OF - timedelta(days=1),
                simulation_eligible_time=REFERENCE_AS_OF - timedelta(days=1),
                numeric_value=value,
                text_value=None,
                unit=version.unit,
                quality_state="complete",
                input_manifest=manifest,
                computation_payload={
                    "formula": "deterministic-reference-formula",
                    "value": str(value),
                },
                lineage={
                    "source_manifest_ids": [],
                    "source_observation_refs": [manifest],
                    "graph_relationship_ids": [],
                    "evidence_ids": [],
                    "grouped_input_manifest": manifest,
                },
                deterministic_seed=9001,
            )


def seed_reference_research(
    session: Session,
    workspace_id: uuid.UUID,
    *,
    application_sha: str = "fixture-v0.9",
    migration_head: str = "2f9e39afd435",
) -> dict[str, Any]:
    companies = _companies(session, workspace_id)
    universe, _ = _universe(session, workspace_id, companies)
    feature_set, definitions = _features(session, workspace_id)
    policy, budgets = _policy(session, workspace_id)
    _materialize(session, workspace_id, companies, definitions)
    run = run_screening(
        session,
        workspace_id=workspace_id,
        universe=universe,
        feature_set=feature_set,
        policy=policy,
        budgets=budgets,
        as_of_time=REFERENCE_AS_OF,
        application_sha=application_sha,
        migration_head=migration_head,
    )
    return {
        "universe_id": str(universe.id),
        "feature_set_id": str(feature_set.id),
        "screening_run_id": str(run.id),
        "feature_count": len(definitions),
        "company_count": len(companies),
        "funnel": {"LEVEL_0": 100, "LEVEL_1": 50, "LEVEL_2": 20, "LEVEL_3": 8, "LEVEL_4": 3},
        "archetype_pipelines": {
            "semiconductor": ["technology", "geopolitical", "energy"],
            "airline": ["energy", "weather", "transportation"],
            "agriculture": ["agriculture", "weather", "energy"],
        },
        "irrelevant_pipelines_skipped": True,
    }
