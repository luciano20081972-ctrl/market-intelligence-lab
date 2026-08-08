from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from packages.database.models import (
    DataRelevanceDecision,
    FeatureDefinition,
    FeatureDefinitionVersion,
    FeatureLineage,
    FeatureMaterializationJob,
    FeatureSet,
    FeatureSetMembership,
    FeatureSnapshot,
    FeatureValue,
    ResearchBudget,
    ResearchBudgetUsage,
    ResearchCandidateState,
    ResearchResolutionPolicy,
    ResearchScreeningDecision,
    ResearchScreeningRun,
    ResearchUniverse,
    ResearchUniverseMembership,
    ResearchUniverseVersion,
)
from packages.research.types import BudgetDecision, FeatureMatrix, ScreeningScore

UNSAFE_QUALITY = {"temporally_unsafe", "failed_computation"}


def _checksum(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _definition_and_version(
    session: Session, feature: str | uuid.UUID, workspace_id: uuid.UUID
) -> tuple[FeatureDefinition, FeatureDefinitionVersion]:
    statement = select(FeatureDefinition).where(FeatureDefinition.workspace_id == workspace_id)
    if isinstance(feature, uuid.UUID):
        statement = statement.where(FeatureDefinition.id == feature)
    else:
        statement = statement.where(FeatureDefinition.feature_key == feature)
    definition = session.scalar(statement)
    if definition is None:
        raise KeyError(f"Unknown feature: {feature}")
    version = session.scalar(
        select(FeatureDefinitionVersion)
        .where(FeatureDefinitionVersion.feature_definition_id == definition.id)
        .order_by(FeatureDefinitionVersion.version.desc())
        .limit(1)
    )
    if version is None:
        raise KeyError(f"Feature has no version: {feature}")
    return definition, version


def get_feature_as_of(
    session: Session,
    feature: str | uuid.UUID,
    entity: uuid.UUID,
    as_of_time: datetime,
    *,
    workspace_id: uuid.UUID,
) -> FeatureValue | None:
    """Return only the latest feature value that was simulation-eligible at T."""
    if as_of_time.tzinfo is None:
        raise ValueError("as_of_time must be timezone-aware")
    _, version = _definition_and_version(session, feature, workspace_id)
    return session.scalar(
        select(FeatureValue)
        .where(
            FeatureValue.workspace_id == workspace_id,
            FeatureValue.feature_version_id == version.id,
            FeatureValue.entity_id == entity,
            FeatureValue.simulation_eligible_time <= as_of_time,
            FeatureValue.observation_time <= as_of_time,
            FeatureValue.quality_state.not_in(UNSAFE_QUALITY),
        )
        .order_by(
            FeatureValue.observation_time.desc(),
            FeatureValue.simulation_eligible_time.desc(),
            FeatureValue.created_at.desc(),
        )
        .limit(1)
    )


def universe_version_as_of(
    session: Session, universe_id: uuid.UUID, as_of_time: datetime
) -> ResearchUniverseVersion | None:
    return session.scalar(
        select(ResearchUniverseVersion)
        .where(
            ResearchUniverseVersion.universe_id == universe_id,
            ResearchUniverseVersion.simulation_eligible_time <= as_of_time,
            ResearchUniverseVersion.effective_from <= as_of_time,
            or_(
                ResearchUniverseVersion.effective_to.is_(None),
                ResearchUniverseVersion.effective_to > as_of_time,
            ),
        )
        .order_by(ResearchUniverseVersion.version.desc())
        .limit(1)
    )


def memberships_as_of(
    session: Session, universe_version_id: uuid.UUID, as_of_time: datetime
) -> list[ResearchUniverseMembership]:
    return list(
        session.scalars(
            select(ResearchUniverseMembership)
            .where(
                ResearchUniverseMembership.universe_version_id == universe_version_id,
                ResearchUniverseMembership.simulation_eligible_time <= as_of_time,
                ResearchUniverseMembership.valid_from <= as_of_time,
                or_(
                    ResearchUniverseMembership.valid_to.is_(None),
                    ResearchUniverseMembership.valid_to > as_of_time,
                ),
            )
            .order_by(ResearchUniverseMembership.entity_id)
        )
    )


def _feature_versions_for_set(
    session: Session, feature_set: FeatureSet
) -> list[tuple[FeatureDefinition, FeatureDefinitionVersion]]:
    rows = session.execute(
        select(FeatureDefinition, FeatureDefinitionVersion)
        .join(
            FeatureSetMembership,
            FeatureSetMembership.feature_version_id == FeatureDefinitionVersion.id,
        )
        .join(
            FeatureDefinition,
            FeatureDefinition.id == FeatureDefinitionVersion.feature_definition_id,
        )
        .where(FeatureSetMembership.feature_set_id == feature_set.id)
        .order_by(FeatureSetMembership.position)
    )
    return [(definition, version) for definition, version in rows]


def get_feature_matrix_as_of(
    session: Session,
    feature_set: FeatureSet | uuid.UUID,
    universe: ResearchUniverse | uuid.UUID,
    as_of_time: datetime,
    *,
    workspace_id: uuid.UUID,
) -> FeatureMatrix:
    """Build a membership- and revision-safe cross-sectional matrix at T."""
    if as_of_time.tzinfo is None:
        raise ValueError("as_of_time must be timezone-aware")
    feature_set_obj = (
        session.get(FeatureSet, feature_set) if isinstance(feature_set, uuid.UUID) else feature_set
    )
    universe_obj = (
        session.get(ResearchUniverse, universe) if isinstance(universe, uuid.UUID) else universe
    )
    if (
        feature_set_obj is None
        or universe_obj is None
        or feature_set_obj.workspace_id != workspace_id
        or universe_obj.workspace_id != workspace_id
    ):
        raise KeyError("Feature set or universe was not found")
    universe_version = universe_version_as_of(session, universe_obj.id, as_of_time)
    if universe_version is None:
        raise KeyError("No universe version was eligible at the requested time")
    members = memberships_as_of(session, universe_version.id, as_of_time)
    definitions = _feature_versions_for_set(session, feature_set_obj)
    values: dict[uuid.UUID, dict[str, Decimal | str | None]] = {}
    missing: dict[uuid.UUID, tuple[str, ...]] = {}
    selected_ids: list[uuid.UUID] = []
    for member in members:
        row: dict[str, Decimal | str | None] = {}
        absent: list[str] = []
        for definition, _ in definitions:
            feature_value = get_feature_as_of(
                session,
                definition.feature_key,
                member.entity_id,
                as_of_time,
                workspace_id=workspace_id,
            )
            if feature_value is None:
                row[definition.feature_key] = None
                absent.append(definition.feature_key)
            else:
                row[definition.feature_key] = (
                    feature_value.numeric_value
                    if feature_value.numeric_value is not None
                    else feature_value.text_value
                )
                selected_ids.append(feature_value.id)
        values[member.entity_id] = row
        missing[member.entity_id] = tuple(absent)
    return FeatureMatrix(
        as_of_time=as_of_time,
        universe_version_id=universe_version.id,
        feature_keys=tuple(item.feature_key for item, _ in definitions),
        entity_ids=tuple(item.entity_id for item in members),
        values=values,
        feature_value_ids=tuple(selected_ids),
        missing=missing,
    )


def create_feature_value(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    feature_version: FeatureDefinitionVersion,
    entity_id: uuid.UUID,
    observation_time: datetime,
    effective_time: datetime,
    calculation_time: datetime,
    simulation_eligible_time: datetime,
    numeric_value: Decimal | None,
    text_value: str | None,
    unit: str,
    quality_state: str,
    input_manifest: dict[str, Any],
    computation_payload: dict[str, Any],
    lineage: dict[str, Any],
    job_id: uuid.UUID | None = None,
    deterministic_seed: int | None = None,
) -> tuple[FeatureValue, bool]:
    if simulation_eligible_time < max(observation_time, effective_time):
        quality_state = "temporally_unsafe"
    input_checksum = _checksum(input_manifest)
    computation_checksum = _checksum(computation_payload)
    existing = session.scalar(
        select(FeatureValue).where(
            FeatureValue.feature_version_id == feature_version.id,
            FeatureValue.entity_id == entity_id,
            FeatureValue.observation_time == observation_time,
            FeatureValue.input_checksum == input_checksum,
        )
    )
    if existing is not None:
        if existing.computation_checksum != computation_checksum:
            raise ValueError("immutable feature identity has a different computation checksum")
        return existing, False
    item = FeatureValue(
        workspace_id=workspace_id,
        feature_version_id=feature_version.id,
        entity_id=entity_id,
        observation_time=observation_time,
        effective_time=effective_time,
        calculation_time=calculation_time,
        simulation_eligible_time=simulation_eligible_time,
        numeric_value=numeric_value,
        text_value=text_value,
        unit=unit,
        quality_state=quality_state,
        quality_flags=[],
        input_checksum=input_checksum,
        computation_checksum=computation_checksum,
        job_id=job_id,
        deterministic_seed=deterministic_seed,
        normalization={},
    )
    session.add(item)
    session.flush()
    lineage_checksum = _checksum(lineage)
    session.add(
        FeatureLineage(
            feature_value_id=item.id,
            source_manifest_ids=lineage.get("source_manifest_ids", []),
            source_observation_refs=lineage.get("source_observation_refs", []),
            graph_relationship_ids=lineage.get("graph_relationship_ids", []),
            evidence_ids=lineage.get("evidence_ids", []),
            grouped_input_manifest=lineage.get("grouped_input_manifest", input_manifest),
            computation_version=feature_version.implementation_version,
            lineage_checksum=lineage_checksum,
        )
    )
    return item, True


def normalize_cross_section(
    values: dict[uuid.UUID, Decimal | None], method: str
) -> dict[uuid.UUID, Decimal | None]:
    available = sorted(
        (value, entity_id) for entity_id, value in values.items() if value is not None
    )
    if not available:
        return dict.fromkeys(values)
    result: dict[uuid.UUID, Decimal | None] = dict.fromkeys(values)
    if method in {"rank", "percentile"}:
        denominator = max(1, len(available) - 1)
        for rank, (_, entity_id) in enumerate(available):
            result[entity_id] = Decimal(rank) / Decimal(denominator)
        return result
    numeric = [float(value) for value, _ in available]
    mean = sum(numeric) / len(numeric)
    variance = sum((value - mean) ** 2 for value in numeric) / len(numeric)
    deviation = math.sqrt(variance)
    for value, entity_id in available:
        normalized = 0.0 if deviation == 0 else (float(value) - mean) / deviation
        if method == "winsorized_zscore":
            normalized = min(3.0, max(-3.0, normalized))
        result[entity_id] = Decimal(str(round(normalized, 10)))
    return result


def score_matrix(matrix: FeatureMatrix) -> list[ScreeningScore]:
    scores: list[ScreeningScore] = []
    for entity_id in matrix.entity_ids:
        row = matrix.values[entity_id]
        numeric = [Decimal(value) for value in row.values() if isinstance(value, Decimal)]
        completeness = Decimal(len(row) - len(matrix.missing[entity_id])) / Decimal(
            max(1, len(row))
        )
        anomaly = sum((abs(value) for value in numeric), Decimal("0")) / Decimal(
            max(1, len(numeric))
        )
        anomaly = min(Decimal("1"), anomaly)
        driver = Decimal(str(row.get("driver_evidence_strength") or "0"))
        freshness = Decimal(str(row.get("source_freshness_score") or "0"))
        components = {
            "data_completeness": completeness,
            "transparent_anomaly": anomaly,
            "driver_evidence": driver,
            "freshness": freshness,
        }
        score = (
            completeness * Decimal("0.35")
            + anomaly * Decimal("0.25")
            + driver * Decimal("0.25")
            + freshness * Decimal("0.15")
        )
        codes = ["DATA_COMPLETE" if completeness == 1 else "MISSING_INFORMATION"]
        if driver >= Decimal("0.6"):
            codes.append("EVIDENCE_BACKED_DRIVER")
        scores.append(
            ScreeningScore(
                entity_id=entity_id,
                score=score.quantize(Decimal("0.00000001")),
                components=components,
                reason_codes=tuple(codes),
                missing_information=matrix.missing[entity_id],
            )
        )
    return sorted(scores, key=lambda item: (-item.score, str(item.entity_id)))


def enforce_budget(
    ranked: list[ScreeningScore], budget: ResearchBudget, requested_level: str
) -> BudgetDecision:
    limit = int(budget.limits.get("maximum_companies", 0))
    accepted = tuple(item.entity_id for item in ranked[:limit])
    deferred = tuple(item.entity_id for item in ranked[limit:])
    return BudgetDecision(
        accepted=accepted,
        deferred=deferred,
        reason=f"{requested_level} maximum population {limit}",
        usage={
            "companies": len(accepted),
            "deferred": len(deferred),
            "api_requests": len(accepted) * int(budget.limits.get("api_requests_per_company", 0)),
        },
    )


def create_snapshot(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    feature_set: FeatureSet,
    matrix: FeatureMatrix,
    application_sha: str,
    migration_head: str,
    policy: ResearchResolutionPolicy,
) -> FeatureSnapshot:
    manifest = {
        "universe_version_id": str(matrix.universe_version_id),
        "feature_set_id": str(feature_set.id),
        "as_of_time": matrix.as_of_time.isoformat(),
        "entity_ids": sorted(str(item) for item in matrix.entity_ids),
        "feature_value_ids": sorted(str(item) for item in matrix.feature_value_ids),
        "application_sha": application_sha,
        "migration_head": migration_head,
        "resolution_policy": policy.version,
        "routing_configuration": "data-relevance-v1",
        "random_seeds": [9001],
        "warnings": [],
    }
    checksum = _checksum(manifest)
    existing = session.scalar(select(FeatureSnapshot).where(FeatureSnapshot.checksum == checksum))
    if existing is not None:
        return existing
    snapshot = FeatureSnapshot(
        workspace_id=workspace_id,
        universe_version_id=matrix.universe_version_id,
        feature_set_id=feature_set.id,
        as_of_time=matrix.as_of_time,
        entity_ids=manifest["entity_ids"],
        feature_value_ids=manifest["feature_value_ids"],
        application_sha=application_sha,
        migration_head=migration_head,
        manifest=manifest,
        checksum=checksum,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def run_screening(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    universe: ResearchUniverse,
    feature_set: FeatureSet,
    policy: ResearchResolutionPolicy,
    budgets: dict[str, ResearchBudget],
    as_of_time: datetime,
    application_sha: str,
    migration_head: str,
) -> ResearchScreeningRun:
    matrix = get_feature_matrix_as_of(
        session, feature_set, universe, as_of_time, workspace_id=workspace_id
    )
    snapshot = create_snapshot(
        session,
        workspace_id=workspace_id,
        feature_set=feature_set,
        matrix=matrix,
        application_sha=application_sha,
        migration_head=migration_head,
        policy=policy,
    )
    ranked = score_matrix(matrix)
    thresholds = ((3, "LEVEL_4"), (8, "LEVEL_3"), (20, "LEVEL_2"), (50, "LEVEL_1"))
    payload = {
        "snapshot": snapshot.checksum,
        "policy": policy.checksum,
        "ranked": [(str(item.entity_id), str(item.score)) for item in ranked],
    }
    checksum = _checksum(payload)
    existing = session.scalar(
        select(ResearchScreeningRun).where(ResearchScreeningRun.checksum == checksum)
    )
    if existing is not None:
        return existing
    run = ResearchScreeningRun(
        workspace_id=workspace_id,
        universe_version_id=matrix.universe_version_id,
        feature_snapshot_id=snapshot.id,
        policy_id=policy.id,
        as_of_time=as_of_time,
        total_candidates=len(ranked),
        promoted=min(50, len(ranked)),
        deferred=max(0, len(ranked) - 50),
        demoted=0,
        rejected=0,
        budget_usage={key: value.limits for key, value in budgets.items()},
        reason_distribution={},
        checksum=checksum,
    )
    session.add(run)
    session.flush()
    for level, budget in budgets.items():
        session.add(
            ResearchBudgetUsage(
                budget_id=budget.id,
                screening_run_id=run.id,
                usage={
                    "level": level,
                    "candidate_limit": budget.limits.get("candidate_limit"),
                    "cost_class": budget.cost_class,
                },
                decision="accepted",
            )
        )
    reasons: Counter[str] = Counter()
    for rank, item in enumerate(ranked):
        level = "LEVEL_0"
        for maximum, candidate_level in thresholds:
            if rank < maximum:
                level = candidate_level
                break
        recommendation = "promote" if level != "LEVEL_0" else "defer"
        level_budget = budgets.get(level)
        reasons.update(item.reason_codes)
        session.add(
            ResearchScreeningDecision(
                screening_run_id=run.id,
                entity_id=item.entity_id,
                score=item.score,
                score_components={key: str(value) for key, value in item.components.items()},
                recommendation=recommendation,
                reason_codes=list(item.reason_codes),
                missing_information=list(item.missing_information),
                budget_impact={
                    "level": level,
                    "cost_class": level_budget.cost_class if level_budget is not None else "free",
                },
            )
        )
        state = session.scalar(
            select(ResearchCandidateState).where(
                ResearchCandidateState.workspace_id == workspace_id,
                ResearchCandidateState.universe_id == universe.id,
                ResearchCandidateState.entity_id == item.entity_id,
                ResearchCandidateState.policy_id == policy.id,
            )
        )
        if state is None:
            state = ResearchCandidateState(
                workspace_id=workspace_id,
                universe_id=universe.id,
                entity_id=item.entity_id,
                policy_id=policy.id,
                current_level=level,
                previous_level=None,
                entered_at=as_of_time,
                promotion_reason=", ".join(item.reason_codes) if level != "LEVEL_0" else None,
                demotion_reason=None,
                supporting_snapshot_id=snapshot.id,
                budget_impact={"rank": rank + 1},
                next_review_time=as_of_time + timedelta(days=30),
            )
            session.add(state)
        else:
            state.previous_level = state.current_level
            state.current_level = level
            state.supporting_snapshot_id = snapshot.id
    run.reason_distribution = dict(reasons)
    return run


def should_materialize(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    company_entity_id: uuid.UUID,
    dataset_id: str,
    override: bool = False,
) -> tuple[bool, str]:
    if override:
        return True, "EXPLICIT_OVERRIDE"
    decision = session.scalar(
        select(DataRelevanceDecision)
        .where(
            DataRelevanceDecision.workspace_id == workspace_id,
            DataRelevanceDecision.company_entity_id == company_entity_id,
            DataRelevanceDecision.dataset_id == dataset_id,
        )
        .order_by(DataRelevanceDecision.created_at.desc())
        .limit(1)
    )
    if decision is not None and decision.decision == "IGNORE":
        return False, "ROUTER_IGNORE"
    return True, decision.decision if decision is not None else "NO_ROUTING_DECISION"


def claim_materialization_job(session: Session) -> FeatureMaterializationJob | None:
    statement = (
        select(FeatureMaterializationJob)
        .where(FeatureMaterializationJob.status == "queued")
        .order_by(FeatureMaterializationJob.requested_at)
        .limit(1)
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    job = session.scalar(statement)
    if job is not None:
        job.status = "running"
        job.started_at = datetime.now(UTC)
    return job
