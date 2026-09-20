"""AUTH-06: import children require a surviving, authorized parent."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from test_workspace_authorization import isolated as isolated
from test_workspace_authorization import set_role

from packages.core.time import utc_now
from packages.database.models import DataManifest, ImportJob, JobEvent


def manifest(job_id, label, retrieved):
    return DataManifest(
        job_id=job_id,
        source_id="alfred",
        dataset_id="alfred.vintages",
        parser_version="test",
        retrieval_time=retrieved,
        raw_object_reference=f"private/{label}.json",
        checksum=label,
        quality_summary={"marker": label},
        license_identifier="test",
    )


@pytest.mark.parametrize("role", ["viewer", "admin"])
def test_manifests_scope_list_filter_detail_and_health(isolated, role):
    client, factory, actor, _, _, jobs = isolated
    set_role(factory, actor, role)
    with factory.begin() as session:
        own = manifest(jobs["own"], "own", utc_now() - timedelta(days=1))
        foreign = manifest(jobs["other"], "foreign", utc_now())
        unowned = manifest(None, "unowned", utc_now() + timedelta(days=1))
        session.add_all([own, foreign, unowned])
        session.flush()
        ids = own.id, foreign.id, unowned.id
    with factory() as session:
        before = [
            tuple(getattr(row, c.key) for c in DataManifest.__table__.columns)
            for row in session.scalars(select(DataManifest).order_by(DataManifest.id))
        ]
    response = client.get("/api/v1/data-manifests")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [str(ids[0])]
    assert "foreign" not in response.text and "unowned" not in response.text
    own_response = client.get(f"/api/v1/data-manifests/{ids[0]}")
    assert own_response.status_code == 200
    assert own_response.json()["job_id"] == str(jobs["own"])
    for target in [ids[1], ids[2], uuid.uuid4()]:
        denied = client.get(f"/api/v1/data-manifests/{target}")
        assert denied.status_code == 404
        assert denied.json() == {"detail": "Data manifest not found"}
    for job in [jobs["other"], uuid.uuid4()]:
        filtered = client.get("/api/v1/data-manifests", params={"job_id": str(job)})
        assert filtered.json() == {"items": [], "total": 0}
    own_filter = client.get("/api/v1/data-manifests", params={"job_id": str(jobs["own"])})
    assert own_filter.json()["total"] == 1
    health = client.get("/api/v1/data-sources/alfred.vintages/health")
    assert health.status_code == 200 and health.json()["latest_manifest_id"] == str(ids[0])
    with factory() as session:
        after = [
            tuple(getattr(row, c.key) for c in DataManifest.__table__.columns)
            for row in session.scalars(select(DataManifest).order_by(DataManifest.id))
        ]
    assert before == after


def test_deleted_manifest_parent_does_not_make_it_global(isolated):
    client, factory, _, _, _, jobs = isolated
    with factory.begin() as session:
        value = manifest(jobs["other"], "deleted-parent", utc_now())
        session.add(value)
        session.flush()
        key = value.id
        session.delete(session.get(ImportJob, jobs["other"]))
    with factory() as session:
        assert session.get(DataManifest, key).job_id is None
    assert client.get(f"/api/v1/data-manifests/{key}").status_code == 404
    assert client.get("/api/v1/data-manifests").json() == {"items": [], "total": 0}
    health = client.get("/api/v1/data-sources/alfred.vintages/health").json()
    assert health["latest_manifest_id"] is None and health["record_count"] == 0


@pytest.mark.parametrize("role", ["viewer", "admin"])
@pytest.mark.parametrize("child", ["events", "quality-report"])
def test_job_children_use_controlled_parent_denial(isolated, role, child):
    client, factory, actor, _, _, jobs = isolated
    set_role(factory, actor, role)
    with factory.begin() as session:
        session.add(JobEvent(job_id=jobs["own"], event_type="test", message="own-event"))
        session.add(JobEvent(job_id=jobs["other"], event_type="test", message="foreign-event"))
    with factory() as session:
        before = [
            tuple(getattr(row, c.key) for c in JobEvent.__table__.columns)
            for row in session.scalars(select(JobEvent).order_by(JobEvent.id))
        ]
    own = client.get(f"/api/v1/import/jobs/{jobs['own']}/{child}")
    assert own.status_code == 200
    if child == "events":
        assert "own-event" in own.text and "foreign-event" not in own.text
    for target in [jobs["other"], uuid.uuid4()]:
        denied = client.get(f"/api/v1/import/jobs/{target}/{child}")
        assert denied.status_code == 404
        assert denied.json() == {"detail": "Import job was not found"}
    assert client.get(f"/api/v1/import/jobs/not-a-uuid/{child}").status_code == 422
    with factory() as session:
        after = [
            tuple(getattr(row, c.key) for c in JobEvent.__table__.columns)
            for row in session.scalars(select(JobEvent).order_by(JobEvent.id))
        ]
    assert before == after
    with factory.begin() as session:
        session.delete(session.get(ImportJob, jobs["own"]))
    assert client.get(f"/api/v1/import/jobs/{jobs['own']}/{child}").status_code == 404


@pytest.mark.parametrize(
    "path", ["/api/v1/data-manifests/not-a-uuid", "/api/v1/data-manifests?job_id=not-a-uuid"]
)
def test_invalid_manifest_identifiers(isolated, path):
    assert isolated[0].get(path).status_code == 422
