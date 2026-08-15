from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from packages.database.models import (
    LEGACY_USER_ID,
    LEGACY_WORKSPACE_ID,
    CompanyDriverEntry,
    CompanyDriverProfile,
    DataRelevanceDecision,
    EconomicEntity,
    EconomicRelationship,
    EntityIdentifier,
    EntityResolutionCandidate,
    EvidenceRecord,
    GraphQualityIssue,
    MacroSeries,
    RelationshipConfidenceComponent,
    RelationshipEvidence,
    SecCompany,
    SecFiling,
    UserProfile,
    Workspace,
    WorkspaceMembership,
)
from packages.database.session import make_session_factory, session_scope
from packages.economic_graph.confidence import (
    CONFIDENCE_FORMULA_VERSION,
    CONFIDENCE_WEIGHTS,
    aggregate_confidence,
)
from packages.economic_graph.fixtures import FIXTURE_TIME, fixture_confidence, fixture_truth
from packages.economic_graph.profiles import process_recompute_job
from packages.economic_graph.sec_extraction import extract_structured_sec_graph
from packages.economic_graph.series_linking import link_economic_series
from packages.economic_graph.service import (
    add_alias,
    attach_identifier,
    create_entity,
    create_evidence,
    create_relationship,
    create_resolution_candidate,
    decide_resolution,
    expire_relationship,
    normalize_identifier,
    queue_recompute,
    scan_graph_quality,
)
from packages.economic_graph.traversal import GraphLimitError, bounded_graph_as_of
from packages.economic_graph.types import ENTITY_TYPES, RELATIONSHIP_TYPES


def _company(session: object, name: str) -> EconomicEntity:
    item = session.scalar(  # type: ignore[attr-defined]
        select(EconomicEntity).where(EconomicEntity.canonical_name == name)
    )
    assert item is not None
    return item


def _evidence(session: object, key: str, eligible: datetime = FIXTURE_TIME) -> EvidenceRecord:
    item, _ = create_evidence(
        session,  # type: ignore[arg-type]
        workspace_id=LEGACY_WORKSPACE_ID,
        source_record_identifier=key,
        publication_time=eligible - timedelta(days=1),
        simulation_eligible_time=eligible,
        evidence_type="test_record",
        checksum=hashlib.sha256(key.encode()).hexdigest(),
        parser_version="test-v1",
        confidence=Decimal("0.9"),
    )
    return item


def test_canonical_entity_and_relationship_catalogs_are_complete() -> None:
    assert len(ENTITY_TYPES) >= 22
    assert {"Company", "Facility", "EconomicSeries", "Event"} <= set(ENTITY_TYPES)
    assert {"HAS_SECURITY", "DEPENDS_ON", "TRACKED_BY_SERIES"} <= set(RELATIONSHIP_TYPES)


def test_identifier_normalization_is_namespace_specific() -> None:
    assert normalize_identifier("cik", "CIK-320193") == "0000320193"
    assert normalize_identifier("ticker", " nvda ") == "NVDA"
    assert normalize_identifier("provider_series", "FRED:CPIAUCSL") == "fred:CPIAUCSL"


def test_entity_alias_and_exact_identifier_are_idempotent(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        alias, created = add_alias(
            session,
            company,
            "Silica Systems, Inc.",
            source="manual fixture",
            simulation_eligible_time=FIXTURE_TIME,
        )
        same, created_again = add_alias(
            session,
            company,
            "Silica Systems, Inc.",
            source="manual fixture",
            simulation_eligible_time=FIXTURE_TIME,
        )
        assert created is True and created_again is False and same.id == alias.id
        identifier = attach_identifier(
            session,
            company,
            namespace="lei",
            value="549300TESTSILICA0001",
            method="exact",
            confidence=Decimal("1"),
            source="fixture",
            resolver_version="test-v1",
            resolved_at=FIXTURE_TIME,
            valid_from=FIXTURE_TIME,
            simulation_eligible_time=FIXTURE_TIME,
        )
        repeated = attach_identifier(
            session,
            company,
            namespace="lei",
            value="549300TESTSILICA0001",
            method="exact",
            confidence=Decimal("1"),
            source="fixture",
            resolver_version="test-v1",
            resolved_at=FIXTURE_TIME,
            valid_from=FIXTURE_TIME,
            simulation_eligible_time=FIXTURE_TIME,
        )
        assert isinstance(identifier, EntityIdentifier) and repeated.id == identifier.id


def test_identifier_ambiguity_creates_candidate_and_quality_issue(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        first = _company(session, "Silica Systems")
        second = _company(session, "Meridian Air")
        attach_identifier(
            session,
            first,
            namespace="figi",
            value="BBG000AMBIGUOUS",
            method="exact",
            confidence=Decimal("0.95"),
            source="fixture",
            resolver_version="test-v1",
            resolved_at=FIXTURE_TIME,
            valid_from=FIXTURE_TIME,
            simulation_eligible_time=FIXTURE_TIME,
        )
        result = attach_identifier(
            session,
            second,
            namespace="figi",
            value="BBG000AMBIGUOUS",
            method="normalized",
            confidence=Decimal("0.60"),
            source="fixture",
            resolver_version="test-v1",
            resolved_at=FIXTURE_TIME,
            valid_from=FIXTURE_TIME,
            simulation_eligible_time=FIXTURE_TIME,
        )
        assert isinstance(result, EntityResolutionCandidate)
        assert result.status == "ambiguous"
        assert (
            session.scalar(
                select(func.count(GraphQualityIssue.id)).where(
                    GraphQualityIssue.issue_type == "ambiguous_identifier"
                )
            )
            == 1
        )


def test_resolution_confirmation_and_rejection_are_explicit(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        confirmed = create_resolution_candidate(
            session,
            company,
            namespace="lei",
            value="549300CONFIRMED0001",
            method="candidate",
            confidence=Decimal("0.75"),
            source="fixture",
            resolver_version="test-v1",
            resolved_at=FIXTURE_TIME,
            valid_from=FIXTURE_TIME,
            simulation_eligible_time=FIXTURE_TIME,
        )
        decision = decide_resolution(
            session,
            confirmed,
            decision="confirmed",
            reason="official record matched",
            user_id=LEGACY_USER_ID,
        )
        assert decision.decision == "confirmed"
        assert (
            session.scalar(
                select(EntityIdentifier).where(
                    EntityIdentifier.normalized_value == "549300CONFIRMED0001"
                )
            )
            is not None
        )
        rejected = create_resolution_candidate(
            session,
            company,
            namespace="lei",
            value="549300REJECTED0001",
            method="candidate",
            confidence=Decimal("0.40"),
            source="fixture",
            resolver_version="test-v1",
            resolved_at=FIXTURE_TIME,
            valid_from=FIXTURE_TIME,
            simulation_eligible_time=FIXTURE_TIME,
        )
        rejected_decision = decide_resolution(
            session,
            rejected,
            decision="rejected",
            reason="conflicting jurisdiction",
            user_id=LEGACY_USER_ID,
        )
        assert rejected_decision.decision == "rejected"


def test_identifier_uniqueness_is_database_enforced(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        values = {
            "workspace_id": LEGACY_WORKSPACE_ID,
            "entity_id": company.id,
            "namespace": "lei",
            "value": "549300DUPLICATE0001",
            "normalized_value": "549300DUPLICATE0001",
            "mapping_method": "test",
            "confidence": Decimal("1"),
            "source": "test",
            "resolver_version": "test-v1",
            "resolved_at": FIXTURE_TIME,
            "valid_from": FIXTURE_TIME,
            "simulation_eligible_time": FIXTURE_TIME,
        }
        session.add_all([EntityIdentifier(**values), EntityIdentifier(**values)])
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_verified_relationship_requires_supporting_evidence(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        target = _company(session, "Meridian Air")
        with pytest.raises(ValueError, match="supporting evidence"):
            create_relationship(
                session,
                subject=company,
                predicate="COMPETES_WITH",
                object_entity=target,
                valid_from=FIXTURE_TIME,
                simulation_eligible_time=FIXTURE_TIME,
                method="test",
                method_version="test-v1",
                components=fixture_confidence(),
                evidence=[],
            )


def test_relationship_confidence_is_decomposed_and_versioned(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        relationship = session.scalar(select(EconomicRelationship).limit(1))
        assert relationship is not None
        components = session.scalars(
            select(RelationshipConfidenceComponent).where(
                RelationshipConfidenceComponent.relationship_id == relationship.id
            )
        ).all()
        assert len(components) == len(CONFIDENCE_WEIGHTS)
        assert {item.formula_version for item in components} == {CONFIDENCE_FORMULA_VERSION}
        values = {item.component: item.value for item in components}
        assert aggregate_confidence(values) == relationship.confidence


def test_supporting_and_contradicting_evidence_are_preserved(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        target = _company(session, "Meridian Air")
        support = _evidence(session, "supporting-competition")
        contradict = _evidence(session, "contradicting-competition")
        relationship, _ = create_relationship(
            session,
            subject=company,
            predicate="COMPETES_WITH",
            object_entity=target,
            valid_from=FIXTURE_TIME + timedelta(seconds=1),
            simulation_eligible_time=FIXTURE_TIME,
            method="test",
            method_version="test-v1",
            components=fixture_confidence(),
            evidence=[
                (support, "supporting", Decimal("1")),
                (contradict, "contradicting", Decimal("0.5")),
            ],
            status="disputed",
        )
        directions = set(
            session.scalars(
                select(RelationshipEvidence.direction).where(
                    RelationshipEvidence.relationship_id == relationship.id
                )
            )
        )
        assert directions == {"supporting", "contradicting"}
        issues = scan_graph_quality(session, workspace_id=LEGACY_WORKSPACE_ID, as_of=FIXTURE_TIME)
        assert "conflicting_evidence" in {item.issue_type for item in issues}


def test_relationship_cannot_precede_supporting_evidence(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        target = _company(session, "Meridian Air")
        future = _evidence(session, "future-evidence", FIXTURE_TIME + timedelta(days=10))
        with pytest.raises(ValueError, match="cannot precede"):
            create_relationship(
                session,
                subject=company,
                predicate="COMPETES_WITH",
                object_entity=target,
                valid_from=FIXTURE_TIME,
                simulation_eligible_time=FIXTURE_TIME,
                method="test",
                method_version="test-v1",
                components=fixture_confidence(),
                evidence=[(future, "supporting", Decimal("1"))],
            )


def test_historical_graph_excludes_future_relationships(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    future_time = FIXTURE_TIME + timedelta(days=30)
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        future_target, _ = create_entity(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            entity_type="Facility",
            canonical_name="Future Fabrication Facility",
            truth=fixture_truth().model_copy(
                update={
                    "publication_time": future_time,
                    "retrieval_time": future_time,
                    "revision_time": future_time,
                    "simulation_eligible_time": future_time,
                    "effective_time": future_time,
                }
            ),
        )
        evidence = _evidence(session, "future-facility", future_time)
        relationship, _ = create_relationship(
            session,
            subject=company,
            predicate="OPERATES",
            object_entity=future_target,
            valid_from=future_time,
            simulation_eligible_time=future_time,
            method="test",
            method_version="test-v1",
            components=fixture_confidence(),
            evidence=[(evidence, "supporting", Decimal("1"))],
        )
        before = bounded_graph_as_of(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            start_entity_id=company.id,
            as_of=future_time - timedelta(microseconds=1),
        )
        at_time = bounded_graph_as_of(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            start_entity_id=company.id,
            as_of=future_time,
        )
        assert str(relationship.id) not in {item["id"] for item in before["relationships"]}
        assert str(relationship.id) in {item["id"] for item in at_time["relationships"]}


def test_traversal_detects_cycles_and_enforces_limits(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        graph = bounded_graph_as_of(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            start_entity_id=company.id,
            as_of=FIXTURE_TIME,
            max_depth=3,
            max_nodes=100,
        )
        assert all(
            len(path["entity_ids"]) == len(set(path["entity_ids"])) for path in graph["paths"]
        )
        with pytest.raises(GraphLimitError, match="node limit"):
            bounded_graph_as_of(
                session,
                workspace_id=LEGACY_WORKSPACE_ID,
                start_entity_id=company.id,
                as_of=FIXTURE_TIME,
                max_depth=3,
                max_nodes=1,
            )
        with pytest.raises(ValueError, match="max_depth"):
            bounded_graph_as_of(
                session,
                workspace_id=LEGACY_WORKSPACE_ID,
                start_entity_id=company.id,
                as_of=FIXTURE_TIME,
                max_depth=8,
            )


def test_relationship_expiry_removes_edge_from_later_graph(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        relationship = session.scalar(
            select(EconomicRelationship).where(EconomicRelationship.subject_entity_id == company.id)
        )
        assert relationship is not None
        expiry = FIXTURE_TIME + timedelta(days=1)
        expire_relationship(relationship, valid_to=expiry)
        graph = bounded_graph_as_of(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            start_entity_id=company.id,
            as_of=expiry,
        )
        assert str(relationship.id) not in {item["id"] for item in graph["relationships"]}


def test_reference_company_profiles_and_routes_differ_materially(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    expected = {
        "Silica Systems": {"technology", "geopolitical", "supply_chain"},
        "Meridian Air": {"energy", "weather_environmental", "transportation"},
        "Harvest Fields Cooperative": {"agriculture", "water", "weather_environmental"},
    }
    with session_scope(factory) as session:
        process_sets: dict[str, set[str]] = {}
        for name, categories in expected.items():
            company = _company(session, name)
            profile = session.scalar(
                select(CompanyDriverProfile).where(
                    CompanyDriverProfile.company_entity_id == company.id
                )
            )
            assert profile is not None
            prominent = set(
                session.scalars(
                    select(CompanyDriverEntry.driver_category).where(
                        CompanyDriverEntry.profile_id == profile.id,
                        CompanyDriverEntry.effective_relevance >= Decimal("0.65"),
                    )
                )
            )
            assert categories <= prominent
            process_sets[name] = set(
                session.scalars(
                    select(DataRelevanceDecision.dataset_id).where(
                        DataRelevanceDecision.profile_id == profile.id,
                        DataRelevanceDecision.decision == "PROCESS",
                    )
                )
            )
        assert "commerce.semiconductors" in process_sets["Silica Systems"]
        assert "faa.airports" in process_sets["Meridian Air"]
        assert "usda.crop-conditions" in process_sets["Harvest Fields Cooperative"]
        assert len({frozenset(value) for value in process_sets.values()}) == 3


def test_manual_override_and_event_recompute_create_new_profile(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        job, created = queue_recompute(
            session,
            company=company,
            trigger_reason="facility_added",
            idempotency_key="silica-facility-added-v1",
        )
        same_job, created_again = queue_recompute(
            session,
            company=company,
            trigger_reason="facility_added",
            idempotency_key="silica-facility-added-v1",
        )
        assert created is True and created_again is False and same_job.id == job.id
        profile = process_recompute_job(
            session,
            job,
            sector="semiconductor",
            user_overrides={"energy": Decimal("0.92")},
        )
        energy = session.scalar(
            select(CompanyDriverEntry).where(
                CompanyDriverEntry.profile_id == profile.id,
                CompanyDriverEntry.driver_category == "energy",
            )
        )
        assert energy is not None and energy.effective_relevance == Decimal("0.92")
        assert job.status == "succeeded"


def test_sec_structured_extraction_is_idempotent_and_conservative(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        sec_company = SecCompany(
            cik="0000999999",
            name="Structured SEC Company",
            tickers=["SSCC"],
            submissions_url="https://data.sec.gov/submissions/CIK0000999999.json",
            facts_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000999999.json",
            retrieved_at=FIXTURE_TIME,
            source_checksum="a" * 64,
        )
        session.add(sec_company)
        session.flush()
        filing = SecFiling(
            company_id=sec_company.id,
            accession_number="0000999999-26-000001",
            form_type="10-K",
            filing_date=date(2026, 1, 10),
            accepted_at=FIXTURE_TIME - timedelta(hours=1),
            source_url="https://sec.example.test/filing",
            retrieved_at=FIXTURE_TIME,
            content_checksum="b" * 64,
            raw_document_reference="sec/raw/fixture",
            parser_version="fixture-v1",
            edgartools_version="unavailable",
            is_amendment=False,
            simulation_eligible_at=FIXTURE_TIME,
        )
        session.add(filing)
        session.flush()
        snapshot = {
            "subsidiaries": ["Structured Subsidiary"],
            "segments": ["Structured Segment"],
            "regions": ["Southwest Region"],
            "suppliers": ["Must Not Be Inferred"],
        }
        entity = extract_structured_sec_graph(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            company=sec_company,
            filing=filing,
            structured=snapshot,
        )
        extract_structured_sec_graph(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            company=sec_company,
            filing=filing,
            structured=snapshot,
        )
        predicates = set(
            session.scalars(
                select(EconomicRelationship.predicate).where(
                    EconomicRelationship.subject_entity_id == entity.id
                )
            )
        )
        assert predicates == {"HAS_SECURITY", "OWNS", "HAS_SEGMENT", "LOCATED_IN"}
        assert (
            session.scalar(
                select(func.count(EconomicEntity.id)).where(
                    EconomicEntity.canonical_name == "Must Not Be Inferred"
                )
            )
            == 0
        )


def test_economic_series_links_through_intermediate_entity(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        region, _ = create_entity(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            entity_type="Region",
            canonical_name="Test Energy Region",
            truth=fixture_truth(),
        )
        series = MacroSeries(
            source_id="fred",
            external_id="TESTSERIES",
            title="Test regional series",
            units="Index",
            frequency="Monthly",
            retrieved_at=FIXTURE_TIME,
        )
        session.add(series)
        session.flush()
        series_entity = link_economic_series(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            context_entity=region,
            series=series,
            provider="fred",
            truth=fixture_truth(),
        )
        relationship = session.scalar(
            select(EconomicRelationship).where(
                EconomicRelationship.subject_entity_id == region.id,
                EconomicRelationship.object_entity_id == series_entity.id,
                EconomicRelationship.predicate == "TRACKED_BY_SERIES",
            )
        )
        assert relationship is not None


def test_workspace_scope_hides_other_graph_entities(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    other_user = uuid.uuid4()
    other_workspace = uuid.uuid4()
    with session_scope(factory) as session:
        session.info["bypass_workspace_scope"] = True
        session.add(
            UserProfile(
                id=other_user,
                auth_subject=f"graph-{other_user}",
                email=f"{other_user}@example.test",
            )
        )
        session.flush()
        session.add(
            Workspace(
                id=other_workspace,
                name="Other Graph Workspace",
                slug=f"graph-{other_workspace}",
                created_by_user_id=other_user,
            )
        )
        session.flush()
        session.add(
            WorkspaceMembership(
                workspace_id=other_workspace,
                user_id=other_user,
                role="owner",
            )
        )
        create_entity(
            session,
            workspace_id=other_workspace,
            entity_type="Company",
            canonical_name="Other Workspace Company",
            truth=fixture_truth(),
        )
    with session_scope(factory) as session:
        session.info["workspace_id"] = LEGACY_WORKSPACE_ID
        assert (
            session.scalar(
                select(EconomicEntity).where(
                    EconomicEntity.canonical_name == "Other Workspace Company"
                )
            )
            is None
        )


def test_graph_api_exposes_bounded_explainable_reference_data(client: object) -> None:
    entities = client.get("/api/v1/entities?entity_type=Company")  # type: ignore[attr-defined]
    assert entities.status_code == 200
    assert entities.json()["total"] == 3
    semiconductor = next(
        item for item in entities.json()["items"] if item["canonical_name"] == "Silica Systems"
    )
    profile = client.get(  # type: ignore[attr-defined]
        f"/api/v1/companies/{semiconductor['id']}/driver-profile"
    )
    assert profile.status_code == 200
    assert profile.json()["scientific_label"].startswith("potential driver")
    paths = client.get(  # type: ignore[attr-defined]
        f"/api/v1/companies/{semiconductor['id']}/driver-paths?max_depth=2&max_nodes=50"
    )
    assert paths.status_code == 200
    assert paths.json()["path_explanations"]
    relevance = client.get(  # type: ignore[attr-defined]
        f"/api/v1/companies/{semiconductor['id']}/data-relevance"
    )
    assert relevance.status_code == 200
    assert any(
        item["dataset_id"] == "commerce.semiconductors" and item["decision"] == "PROCESS"
        for item in relevance.json()["items"]
    )


def test_resolution_admin_api_records_manual_decision(engine: object, client: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        company = _company(session, "Silica Systems")
        candidate = create_resolution_candidate(
            session,
            company,
            namespace="lei",
            value="549300APIREVIEW0001",
            method="candidate",
            confidence=Decimal("0.8"),
            source="fixture",
            resolver_version="test-v1",
            resolved_at=FIXTURE_TIME,
            valid_from=FIXTURE_TIME,
            simulation_eligible_time=FIXTURE_TIME,
        )
        candidate_id = candidate.id
    response = client.post(  # type: ignore[attr-defined]
        f"/api/v1/entity-resolution/{candidate_id}/confirm",
        json={"reason": "official identifier reviewed"},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "confirmed"
