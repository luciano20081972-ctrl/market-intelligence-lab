from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from packages.database.models import (
    LEGACY_WORKSPACE_ID,
    EconomicEntity,
    FeatureDefinition,
    FeatureDefinitionVersion,
    FeatureLineage,
    FeatureMaterializationJob,
    FeatureSet,
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
from packages.database.session import make_session_factory, session_scope
from packages.research.fixtures import REFERENCE_AS_OF, seed_reference_research
from packages.research.service import (
    claim_materialization_job,
    create_feature_value,
    enforce_budget,
    get_feature_as_of,
    get_feature_matrix_as_of,
    memberships_as_of,
    normalize_cross_section,
    score_matrix,
    should_materialize,
    universe_version_as_of,
)
from packages.research.types import ScreeningScore


def _seed(engine: object) -> tuple[dict[str, object], object]:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        result = seed_reference_research(session, LEGACY_WORKSPACE_ID)
    return result, factory


def test_reference_fixture_builds_reproducible_100_company_funnel(engine: object) -> None:
    result, factory = _seed(engine)
    assert result["company_count"] == 100
    assert result["feature_count"] == 15
    assert result["funnel"] == {
        "LEVEL_0": 100,
        "LEVEL_1": 50,
        "LEVEL_2": 20,
        "LEVEL_3": 8,
        "LEVEL_4": 3,
    }
    assert result["irrelevant_pipelines_skipped"] is True
    with session_scope(factory) as session:  # type: ignore[arg-type]
        assert session.scalar(select(func.count(FeatureValue.id))) == 1500
        assert session.scalar(select(func.count(FeatureLineage.id))) == 1500
        assert session.scalar(select(func.count(ResearchCandidateState.id))) == 100
        assert session.scalar(select(func.count(ResearchBudgetUsage.id))) == 5
        levels = dict(
            session.execute(
                select(ResearchCandidateState.current_level, func.count())
                .group_by(ResearchCandidateState.current_level)
                .order_by(ResearchCandidateState.current_level)
            ).all()
        )
        assert levels == {
            "LEVEL_0": 50,
            "LEVEL_1": 30,
            "LEVEL_2": 12,
            "LEVEL_3": 5,
            "LEVEL_4": 3,
        }


def test_feature_matrix_and_snapshot_are_point_in_time_and_reproducible(engine: object) -> None:
    result, factory = _seed(engine)
    with session_scope(factory) as session:  # type: ignore[arg-type]
        universe = session.get(ResearchUniverse, uuid.UUID(str(result["universe_id"])))
        feature_set = session.get(FeatureSet, uuid.UUID(str(result["feature_set_id"])))
        assert universe is not None and feature_set is not None
        first = get_feature_matrix_as_of(
            session,
            feature_set,
            universe,
            REFERENCE_AS_OF,
            workspace_id=LEGACY_WORKSPACE_ID,
        )
        second = get_feature_matrix_as_of(
            session,
            feature_set,
            universe,
            REFERENCE_AS_OF,
            workspace_id=LEGACY_WORKSPACE_ID,
        )
        assert len(first.entity_ids) == 100
        assert len(first.feature_keys) == 15
        assert first.values == second.values
        assert first.feature_value_ids == second.feature_value_ids
        assert all(not missing for missing in first.missing.values())
        runs = list(session.scalars(select(ResearchScreeningRun)))
        assert len(runs) == 1 and runs[0].total_candidates == 100
        original_checksum = runs[0].checksum
        repeat = seed_reference_research(session, LEGACY_WORKSPACE_ID)
        repeated_run = session.get(ResearchScreeningRun, uuid.UUID(str(repeat["screening_run_id"])))
        assert repeated_run is not None and repeated_run.checksum == original_checksum
        assert session.scalar(select(func.count(ResearchScreeningRun.id))) == 1


def test_future_feature_revision_cannot_leak_into_historical_retrieval(engine: object) -> None:
    result, factory = _seed(engine)
    with session_scope(factory) as session:  # type: ignore[arg-type]
        universe = session.get(ResearchUniverse, uuid.UUID(str(result["universe_id"])))
        assert universe is not None
        version = universe_version_as_of(session, universe.id, REFERENCE_AS_OF)
        assert version is not None
        entity_id = memberships_as_of(session, version.id, REFERENCE_AS_OF)[0].entity_id
        definition = session.scalar(
            select(FeatureDefinition).where(FeatureDefinition.feature_key == "revenue_growth_yoy")
        )
        assert definition is not None
        feature_version = session.scalar(
            select(FeatureDefinitionVersion).where(
                FeatureDefinitionVersion.feature_definition_id == definition.id
            )
        )
        assert feature_version is not None
        before = get_feature_as_of(
            session,
            definition.feature_key,
            entity_id,
            REFERENCE_AS_OF,
            workspace_id=LEGACY_WORKSPACE_ID,
        )
        assert before is not None
        future, created = create_feature_value(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            feature_version=feature_version,
            entity_id=entity_id,
            observation_time=REFERENCE_AS_OF - timedelta(days=10),
            effective_time=REFERENCE_AS_OF - timedelta(days=10),
            calculation_time=REFERENCE_AS_OF + timedelta(days=30),
            simulation_eligible_time=REFERENCE_AS_OF + timedelta(days=30),
            numeric_value=Decimal("999"),
            text_value=None,
            unit="ratio",
            quality_state="revised",
            input_manifest={"future_revision": True},
            computation_payload={"value": "999"},
            lineage={"source_observation_refs": [{"alfred_vintage": "future"}]},
        )
        assert created is True
        historical = get_feature_as_of(
            session,
            definition.feature_key,
            entity_id,
            REFERENCE_AS_OF,
            workspace_id=LEGACY_WORKSPACE_ID,
        )
        current = get_feature_as_of(
            session,
            definition.feature_key,
            entity_id,
            REFERENCE_AS_OF + timedelta(days=31),
            workspace_id=LEGACY_WORKSPACE_ID,
        )
        assert historical is not None and historical.id == before.id
        assert current is not None and current.id == future.id


def test_future_universe_membership_and_graph_inputs_cannot_leak(engine: object) -> None:
    result, factory = _seed(engine)
    with session_scope(factory) as session:  # type: ignore[arg-type]
        universe = session.get(ResearchUniverse, uuid.UUID(str(result["universe_id"])))
        assert universe is not None
        historical = universe_version_as_of(session, universe.id, REFERENCE_AS_OF)
        assert historical is not None and historical.version == 1
        future = ResearchUniverseVersion(
            universe_id=universe.id,
            version=2,
            effective_from=REFERENCE_AS_OF - timedelta(days=1),
            effective_to=None,
            simulation_eligible_time=REFERENCE_AS_OF + timedelta(days=60),
            membership_checksum="f" * 64,
            provenance={"future_constituents": True},
        )
        session.add(future)
        session.flush()
        entity = session.scalar(
            select(EconomicEntity).where(EconomicEntity.entity_type == "Company")
        )
        assert entity is not None
        session.add(
            ResearchUniverseMembership(
                universe_version_id=future.id,
                entity_id=entity.id,
                valid_from=REFERENCE_AS_OF - timedelta(days=1),
                valid_to=None,
                simulation_eligible_time=REFERENCE_AS_OF + timedelta(days=60),
                source_manifest_id=None,
                provenance={"future_graph_edge": True, "future_sec_information": True},
            )
        )
        assert universe_version_as_of(session, universe.id, REFERENCE_AS_OF).id == historical.id
        assert (
            universe_version_as_of(session, universe.id, REFERENCE_AS_OF + timedelta(days=61)).id
            == future.id
        )


def test_immutable_feature_identity_allows_revision_but_rejects_recomputation(
    engine: object,
) -> None:
    _, factory = _seed(engine)
    with session_scope(factory) as session:  # type: ignore[arg-type]
        existing = session.scalar(select(FeatureValue))
        assert existing is not None
        version = session.get(FeatureDefinitionVersion, existing.feature_version_id)
        assert version is not None
        kwargs = {
            "workspace_id": LEGACY_WORKSPACE_ID,
            "feature_version": version,
            "entity_id": existing.entity_id,
            "observation_time": existing.observation_time,
            "effective_time": existing.effective_time,
            "calculation_time": existing.calculation_time,
            "simulation_eligible_time": existing.simulation_eligible_time,
            "numeric_value": existing.numeric_value,
            "text_value": existing.text_value,
            "unit": existing.unit,
            "quality_state": existing.quality_state,
            "input_manifest": {"company_index": 0, "feature": "different"},
            "lineage": {},
        }
        created, was_created = create_feature_value(
            session, computation_payload={"value": "revision"}, **kwargs
        )
        assert was_created is True and created.id != existing.id
        repeated, repeated_created = create_feature_value(
            session, computation_payload={"value": "revision"}, **kwargs
        )
        assert repeated.id == created.id and repeated_created is False
        with pytest.raises(ValueError, match="immutable feature identity"):
            create_feature_value(
                session, computation_payload={"value": "changed-computation"}, **kwargs
            )


def test_normalization_and_budget_are_deterministic_and_population_safe(engine: object) -> None:
    entity_ids = [uuid.UUID(int=index + 1) for index in range(5)]
    values = {entity_id: Decimal(index) for index, entity_id in enumerate(entity_ids)}
    percentile = normalize_cross_section(values, "percentile")
    zscore = normalize_cross_section(values, "zscore")
    assert percentile[entity_ids[0]] == Decimal("0")
    assert percentile[entity_ids[-1]] == Decimal("1")
    assert zscore == normalize_cross_section(values, "zscore")
    _, factory = _seed(engine)
    with session_scope(factory) as session:  # type: ignore[arg-type]
        budget = session.scalar(select(ResearchBudget).where(ResearchBudget.level == "LEVEL_1"))
        assert budget is not None
        ranked = [
            ScreeningScore(
                entity_id=uuid.UUID(int=index + 1),
                score=Decimal(500 - index),
                components={},
                reason_codes=(),
                missing_information=(),
            )
            for index in range(500)
        ]
        decision = enforce_budget(ranked, budget, "LEVEL_1")
        assert len(decision.accepted) == 50
        assert len(decision.deferred) == 450
        assert decision.accepted == tuple(item.entity_id for item in ranked[:50])


def test_router_skip_and_materialization_job_claim(engine: object) -> None:
    _, factory = _seed(engine)
    with session_scope(factory) as session:  # type: ignore[arg-type]
        decision = session.execute(
            select(EconomicEntity.id)
            .join(
                ResearchCandidateState,
                ResearchCandidateState.entity_id == EconomicEntity.id,
            )
            .limit(1)
        ).scalar_one()
        allowed, reason = should_materialize(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            company_entity_id=decision,
            dataset_id="unregistered.fixture",
        )
        assert allowed is True and reason == "NO_ROUTING_DECISION"
        feature_set = session.scalar(select(FeatureSet))
        universe_version = session.scalar(select(ResearchUniverseVersion))
        assert feature_set is not None and universe_version is not None
        session.add(
            FeatureMaterializationJob(
                workspace_id=LEGACY_WORKSPACE_ID,
                feature_set_id=feature_set.id,
                universe_version_id=universe_version.id,
                mode="incremental",
                status="queued",
                scope={},
                checkpoint={},
                idempotency_key="test-claim-v1",
            )
        )
        session.flush()
        claimed = claim_materialization_job(session)
        assert claimed is not None and claimed.status == "running"


def test_reference_research_api_is_workspace_scoped_and_read_only_surface(client: object) -> None:
    response = client.post("/api/v1/research/screening-runs/reference-fixture")  # type: ignore[attr-defined]
    assert response.status_code == 200
    assert response.json()["funnel"]["LEVEL_4"] == 3
    for path, expected in (
        ("/api/v1/features", 15),
        ("/api/v1/feature-sets", 1),
        ("/api/v1/research-universes", 1),
        ("/api/v1/research/screening-runs", 1),
        ("/api/v1/research/candidates", 100),
        ("/api/v1/research/budgets", 5),
    ):
        payload = client.get(path)  # type: ignore[attr-defined]
        assert payload.status_code == 200
        assert payload.json()["total"] == expected
    values = client.get("/api/v1/feature-values?page_size=5")  # type: ignore[attr-defined]
    assert values.status_code == 200
    assert values.json()["point_in_time_safe"] is True
    lineage = client.get(f"/api/v1/feature-values/{values.json()['items'][0]['id']}/lineage")  # type: ignore[attr-defined]
    assert lineage.status_code == 200
    assert lineage.json()["computation_version"] == "mil-feature-v1"


def test_scientific_vocabulary_never_labels_screening_as_alpha(engine: object) -> None:
    result, factory = _seed(engine)
    with session_scope(factory) as session:  # type: ignore[arg-type]
        run = session.get(ResearchScreeningRun, uuid.UUID(str(result["screening_run_id"])))
        assert run is not None
        decisions = list(
            session.scalars(
                select(ResearchScreeningDecision).where(
                    ResearchScreeningDecision.screening_run_id == run.id
                )
            )
        )
        serialized = str([item.reason_codes for item in decisions]).lower()
        assert "buy" not in serialized
        assert "sell" not in serialized
        assert "expected return" not in serialized
        assert "alpha" not in serialized


def test_score_matrix_is_stable_for_identical_point_in_time_data(engine: object) -> None:
    result, factory = _seed(engine)
    with session_scope(factory) as session:  # type: ignore[arg-type]
        universe = session.get(ResearchUniverse, uuid.UUID(str(result["universe_id"])))
        feature_set = session.get(FeatureSet, uuid.UUID(str(result["feature_set_id"])))
        assert universe is not None and feature_set is not None
        matrix = get_feature_matrix_as_of(
            session,
            feature_set,
            universe,
            REFERENCE_AS_OF,
            workspace_id=LEGACY_WORKSPACE_ID,
        )
        first = score_matrix(matrix)
        second = score_matrix(matrix)
        assert first == second
        assert len(first) == 100
        assert all(item.score >= 0 for item in first)


def test_policy_and_configuration_are_versioned(engine: object) -> None:
    _, factory = _seed(engine)
    with session_scope(factory) as session:  # type: ignore[arg-type]
        policy = session.scalar(select(ResearchResolutionPolicy))
        assert policy is not None
        assert policy.version == "progressive-resolution-v1"
        assert policy.configuration["levels"]["LEVEL_4"]["meaning"].startswith("future AI")
        assert len(policy.checksum) == 64
