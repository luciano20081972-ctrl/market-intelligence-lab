"""AUTH-08: a visible object does not authorize its related-resource IDs."""

import json
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from test_import_authorization import manifest
from test_workspace_authorization import isolated as isolated
from test_workspace_authorization import set_role

from packages.core.time import utc_now
from packages.database.models import (
    DataManifest,
    EnergyObservation,
    EnergySeries,
    ImportBatch,
    ImportError,
    ImportJob,
    ImportSchedule,
    MacroObservation,
    MacroSeries,
    ScheduleRun,
)


def snapshot(factory):
    models = (DataManifest, ImportJob, ImportBatch, ImportError, ScheduleRun)
    with factory() as session:
        return {
            model.__name__: [
                tuple(getattr(row, c.key) for c in model.__table__.columns)
                for row in session.scalars(select(model).order_by(model.id))
            ]
            for model in models
        }


def record(response, before, factory):
    after = snapshot(factory)
    print(
        json.dumps(
            {
                "path": str(response.request.url),
                "status": response.status_code,
                "response": response.json(),
                "before": before,
                "after": after,
            },
            default=str,
        )
    )
    assert before == after


@pytest.mark.parametrize("parent_kind", ["own", "other", "null", "orphan", "none"])
def test_manifest_relationship_visibility(isolated, parent_kind):
    client, factory, _, _, _, jobs = isolated
    with factory.begin() as session:
        parent = manifest(jobs.get(parent_kind), "lineage-parent", utc_now())
        if parent_kind == "orphan":
            job = session.get(ImportJob, jobs["other"])
            parent.job_id = job.id
        session.add(parent)
        session.flush()
        child = manifest(jobs["own"], "lineage-child", utc_now() + timedelta(days=1))
        child.parent_manifest_id = None if parent_kind == "none" else parent.id
        session.add(child)
        session.flush()
        parent_id, child_id = parent.id, child.id
        if parent_kind == "orphan":
            session.delete(job)
    before = snapshot(factory)
    expected = str(parent_id) if parent_kind == "own" else None
    detail = client.get(f"/api/v1/data-manifests/{child_id}")
    listing = client.get("/api/v1/data-manifests")
    health = client.get("/api/v1/data-sources/alfred.vintages/health")
    for response in (detail, listing, health):
        record(response, before, factory)
    assert detail.status_code == listing.status_code == health.status_code == 200
    items = listing.json()["items"]
    assert detail.json()["parent_manifest_id"] == expected
    assert next(x for x in items if x["id"] == str(child_id))["parent_manifest_id"] == expected
    assert listing.json()["total"] == (2 if parent_kind == "own" else 1)
    assert health.json()["latest_manifest_id"] == str(child_id)
    if parent_kind != "own":
        assert str(parent_id) not in detail.text + listing.text + health.text
        assert client.get(f"/api/v1/data-manifests/{parent_id}").status_code == 404
    else:
        assert client.get(f"/api/v1/data-manifests/{parent_id}").status_code == 200
    assert snapshot(factory) == before
    with factory() as session:
        # HTTP redaction must not mutate trusted internal historical lineage.
        assert session.get(DataManifest, child_id).parent_manifest_id == (
            None if parent_kind == "none" else parent_id
        )


def test_manifest_lineage_integrity(isolated):
    _, factory, _, _, _, jobs = isolated
    with pytest.raises(IntegrityError), factory.begin() as session:
        child = manifest(jobs["own"], "missing-parent", utc_now())
        child.parent_manifest_id = uuid.uuid4()
        session.add(child)
        session.flush()
    with factory.begin() as session:
        parent = manifest(jobs["own"], "restricted-parent", utc_now())
        session.add(parent)
        session.flush()
        child = manifest(jobs["own"], "restricted-child", utc_now())
        child.parent_manifest_id = parent.id
        session.add(child)
        key = parent.id
    before = snapshot(factory)
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.delete(session.get(DataManifest, key))
        session.flush()
    assert snapshot(factory) == before


@pytest.mark.parametrize("side", ["own", "other"])
def test_error_batch_relationship_visibility(isolated, side):
    client, factory, _, _, _, jobs = isolated
    with factory.begin() as session:
        batch = ImportBatch(
            job_id=jobs[side],
            sequence=1,
            status="failed",
            request_timestamp=utc_now(),
            checksum="batch-reference",
        )
        session.add(batch)
        session.flush()
        error = ImportError(
            job_id=jobs["own"], batch_id=batch.id, error_code="TEST", message="own error"
        )
        session.add(error)
        session.flush()
        batch_id, error_id = batch.id, error.id
    before = snapshot(factory)
    response = client.get("/api/v1/import/errors", params={"job_id": str(jobs["own"])})
    record(response, before, factory)
    assert response.status_code == 200
    item = next(x for x in response.json()["items"] if x["id"] == str(error_id))
    assert item["batch_id"] == (str(batch_id) if side == "own" else None)
    assert response.json()["meta"]["total"] == 1
    if side == "other":
        assert str(batch_id) not in response.text
        assert client.get(f"/api/v1/import/jobs/{jobs[side]}").status_code == 404
    assert snapshot(factory) == before


@pytest.mark.parametrize("side", ["own", "other"])
def test_schedule_run_job_relationship_visibility(isolated, side):
    client, factory, actor, _, _, jobs = isolated
    set_role(factory, actor, "admin")
    with factory.begin() as session:
        own_job = session.get(ImportJob, jobs["own"])
        schedule = ImportSchedule(
            workspace_id=own_job.workspace_id,
            provider_id=own_job.provider_id,
            name="relationship",
            is_enabled=False,
            next_run_at=utc_now(),
        )
        session.add(schedule)
        session.flush()
        session.add(
            ScheduleRun(schedule_id=schedule.id, job_id=jobs[side], scheduled_for=utc_now())
        )
        schedule_id = schedule.id
    before = snapshot(factory)
    response = client.post(f"/api/v1/import/schedules/{schedule_id}/run-now")
    record(response, before, factory)
    assert response.status_code == 200
    assert response.json()["job_id"] == (str(jobs[side]) if side == "own" else None)
    assert snapshot(factory) == before


@pytest.mark.parametrize("kind", ["macro", "energy"])
@pytest.mark.parametrize("side", ["own", "other", "null"])
def test_observation_manifest_relationship_visibility(isolated, kind, side):
    client, factory, _, _, _, jobs = isolated
    now = utc_now()
    with factory.begin() as session:
        parent = manifest(jobs.get(side), "observation-provenance", now)
        series_cls = MacroSeries if kind == "macro" else EnergySeries
        series = series_cls(
            source_id="test",
            external_id="relation",
            title="public",
            units="units",
            frequency="day",
            retrieved_at=now,
        )
        if kind == "energy":
            series.geography = "US"
        session.add_all([parent, series])
        session.flush()
        model = MacroObservation if kind == "macro" else EnergyObservation
        session.add(
            model(
                series_id=series.id,
                manifest_id=parent.id,
                source_value="42",
                numeric_value=42,
                event_time=now,
                observation_time=now,
                publication_time=now,
                retrieval_time=now,
                effective_time=now,
                revision_time=now,
                simulation_eligible_time=now,
            )
        )
        series_id, parent_id = series.id, parent.id
    before = snapshot(factory)
    paths = [f"/api/v1/{kind}/series/{series_id}/observations"]
    if kind == "macro":
        paths.append(f"/api/v1/macro/series/{series_id}/as-of")
    for path in paths:
        response = client.get(path, params={"as_of": (now + timedelta(days=1)).isoformat()})
        record(response, before, factory)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        row = response.json()["items"][0]
        assert row["source_value"] == "42"
        assert row["manifest_id"] == (str(parent_id) if side == "own" else None)
        if side != "own":
            assert str(parent_id) not in response.text
    assert snapshot(factory) == before


def test_manifest_parent_lookup_is_batched(isolated):
    client, factory, _, _, _, jobs = isolated
    with factory.begin() as session:
        parent = manifest(jobs["own"], "batch-parent", utc_now())
        session.add(parent)
        session.flush()
        for number in range(30):
            child = manifest(jobs["own"], f"child-{number}", utc_now())
            child.parent_manifest_id = parent.id
            session.add(child)
    statements = []
    engine = factory.kw["bind"]

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT") and "data_manifests" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get("/api/v1/data-manifests")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200 and response.json()["total"] == 31
    assert len(statements) <= 2
