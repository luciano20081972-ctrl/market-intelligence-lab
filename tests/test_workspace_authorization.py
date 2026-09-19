"""AUTH-04: exercise real native sessions and persisted tenant/action boundaries."""

from __future__ import annotations

import ast
import logging
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, update
from sqlalchemy.exc import OperationalError

from apps.api.main import create_app
from packages.auth import native
from packages.core.config import Settings
from packages.core.time import utc_now
from packages.database.base import Base
from packages.database.models import (
    LEGACY_WORKSPACE_ID,
    Asset,
    ImportError,
    ImportJob,
    JobLease,
    OperationalAlert,
    PaperOrder,
    PaperPortfolio,
    Provider,
    ScheduledTaskDefinition,
    ScheduledTaskOccurrence,
    UserProfile,
    WorkerInstance,
    Workspace,
    WorkspaceMembership,
)
from packages.database.session import make_session_factory
from packages.market_data.operations import recover_abandoned_jobs
from packages.security.authorization import permission_for_request
from packages.security.tenant import workspace_models

ORIGIN = "https://auth04.example.test:8443"
PASSWORD = "disposable-auth04-password"  # noqa: S105


@pytest.fixture
def isolated(engine):
    factory = make_session_factory(engine)
    actor, other_owner, other_workspace = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    occurrences = {}
    definitions = {}
    jobs = {}
    with factory.begin() as session:
        session.add_all(
            [
                UserProfile(id=actor, auth_subject="auth04-viewer", email="viewer@example.test"),
                UserProfile(
                    id=other_owner, auth_subject="auth04-other", email="other@example.test"
                ),
            ]
        )
        session.flush()
        session.add(
            Workspace(
                id=other_workspace,
                name="Other tenant",
                slug="auth04-other",
                created_by_user_id=other_owner,
            )
        )
        session.flush()
        session.add_all(
            [
                WorkspaceMembership(workspace_id=LEGACY_WORKSPACE_ID, user_id=actor, role="viewer"),
                WorkspaceMembership(
                    workspace_id=other_workspace, user_id=other_owner, role="owner"
                ),
            ]
        )
        provider = session.scalar(select(Provider.id))
        for label, workspace in [
            ("own", LEGACY_WORKSPACE_ID),
            ("other", other_workspace),
            ("system", None),
        ]:
            definition = ScheduledTaskDefinition(
                workspace_id=workspace,
                name=f"auth04-{label}",
                task_type="fixture",
                schedule_type="INTERVAL",
                next_due_at=utc_now(),
                checksum=label,
            )
            session.add(definition)
            session.flush()
            occurrence = ScheduledTaskOccurrence(
                workspace_id=workspace,
                definition_id=definition.id,
                scheduled_for=utc_now(),
                status="QUARANTINED",
                idempotency_key=f"auth04-{label}",
            )
            session.add(occurrence)
            session.add(
                OperationalAlert(
                    workspace_id=workspace,
                    severity="WARNING",
                    category="TEST",
                    deduplication_key=f"auth04-{label}",
                    summary=f"auth04-{label}",
                )
            )
            if workspace is not None:
                job = ImportJob(
                    workspace_id=workspace, provider_id=provider, mode="historical", status="failed"
                )
                session.add(job)
                session.flush()
                jobs[label] = job.id
            session.flush()
            definitions[label], occurrences[label] = definition.id, occurrence.id
    native.enroll(factory, engine, actor, "auth04-viewer", PASSWORD)
    settings = Settings(environment="test", auth_mode="native", auth_allowed_origins=[ORIGIN])
    with TestClient(create_app(settings, engine), headers={"Origin": ORIGIN}) as client:
        response = client.post(
            "/api/v1/auth/login", json={"login": "auth04-viewer", "password": PASSWORD}
        )
        assert response.status_code == 200
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        yield client, factory, actor, definitions, occurrences, jobs


def set_role(factory, actor, role):
    with factory.begin() as session:
        session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == actor,
                WorkspaceMembership.workspace_id == LEGACY_WORKSPACE_ID,
            )
        ).role = role


def snapshot(factory, object_id):
    with factory() as session:
        item = session.get(ScheduledTaskOccurrence, object_id)
        return tuple(getattr(item, column.key) for column in item.__table__.columns)


@pytest.mark.parametrize("role", ["owner", "admin", "viewer"])
def test_lists_hide_foreign_and_system_work(isolated, role):
    client, factory, actor, definitions, occurrences, _ = isolated
    set_role(factory, actor, role)
    for path, ids in [("scheduled-tasks", definitions), ("occurrences", occurrences)]:
        response = client.get(f"/api/v1/operations/{path}")
        assert response.status_code == 200
        visible = {row["id"] for row in response.json()}
        assert str(ids["own"]) in visible
        assert str(ids["other"]) not in visible and str(ids["system"]) not in visible
    alerts = client.get("/api/v1/operations/alerts")
    assert "auth04-own" in alerts.text
    assert "auth04-other" not in alerts.text and "auth04-system" not in alerts.text


@pytest.mark.parametrize("role", ["owner", "admin", "viewer"])
@pytest.mark.parametrize("action", ["dismiss", "retry", "supersede"])
def test_known_foreign_ids_never_grant_mutation(isolated, role, action):
    client, factory, actor, _, occurrences, _ = isolated
    set_role(factory, actor, role)
    for label in ("other", "system"):
        key = occurrences[label]
        before = snapshot(factory, key)
        response = client.post(f"/api/v1/operations/occurrences/{key}/{action}")
        assert response.status_code == (403 if role == "viewer" else 404)
        assert snapshot(factory, key) == before
        # No standalone GET/delete/cancel endpoint exists; none may expose the object.
        assert client.get(f"/api/v1/operations/occurrences/{key}").status_code == 404


@pytest.mark.parametrize("role", ["owner", "admin", "member", "viewer"])
@pytest.mark.parametrize("action", ["dismiss", "retry", "supersede"])
def test_same_workspace_action_policy(isolated, role, action):
    client, factory, actor, _, occurrences, _ = isolated
    set_role(factory, actor, role)
    key = occurrences["own"]
    before = snapshot(factory, key)
    response = client.post(f"/api/v1/operations/occurrences/{key}/{action}")
    assert response.status_code == (403 if role == "viewer" else 200)
    if role == "viewer":
        assert snapshot(factory, key) == before
    else:
        assert response.json()["status"] == ("RETRY_WAIT" if action == "retry" else "CANCELLED")
        assert client.post(f"/api/v1/operations/occurrences/{key}/{action}").status_code == 409


def test_permission_downgrade_applies_to_existing_session(isolated):
    client, factory, actor, _, occurrences, _ = isolated
    set_role(factory, actor, "admin")
    assert client.get("/api/v1/operations/occurrences").status_code == 200
    set_role(factory, actor, "viewer")
    before = snapshot(factory, occurrences["own"])
    assert (
        client.post(f"/api/v1/operations/occurrences/{occurrences['own']}/retry").status_code == 403
    )
    assert snapshot(factory, occurrences["own"]) == before


def test_unknown_malformed_and_unsupported_actions(isolated):
    client, factory, actor, _, occurrences, _ = isolated
    set_role(factory, actor, "admin")
    assert client.post(f"/api/v1/operations/occurrences/{uuid.uuid4()}/retry").status_code == 404
    assert client.post("/api/v1/operations/occurrences/not-a-uuid/retry").status_code == 422
    key = occurrences["own"]
    before = snapshot(factory, key)
    assert client.post(f"/api/v1/operations/occurrences/{key}/cancel").status_code == 422
    assert client.delete(f"/api/v1/operations/occurrences/{key}").status_code in (404, 405)
    assert snapshot(factory, key) == before


def test_parallel_resolution_has_one_winner(isolated):
    client, factory, actor, _, occurrences, _ = isolated
    set_role(factory, actor, "admin")
    key = occurrences["own"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda action: (
                    client.post(f"/api/v1/operations/occurrences/{key}/{action}").status_code
                ),
                ["retry", "dismiss"],
            )
        )
    assert sorted(statuses) == [200, 409]


@pytest.mark.parametrize("action", ["cancel", "restart", "retry"])
def test_viewer_cannot_manage_imports(isolated, action):
    client, factory, _, _, _, jobs = isolated
    for key in jobs.values():
        with factory() as session:
            row = session.get(ImportJob, key)
            before = (row.status, row.cancel_requested, row.attempt)
        assert client.post(f"/api/v1/import/jobs/{key}/{action}").status_code == 403
        with factory() as session:
            row = session.get(ImportJob, key)
            assert (row.status, row.cancel_requested, row.attempt) == before
    assert client.post("/api/v1/operations/recover-abandoned").status_code == 403
    assert client.post("/api/v1/paper/plans", json={}).status_code == 403


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_bulk_writes_cannot_target_foreign_scope(isolated, operation):
    _, factory, _, _, occurrences, _ = isolated
    key = occurrences["other"]
    before = snapshot(factory, key)
    with factory.begin() as session:
        session.info["workspace_id"] = LEGACY_WORKSPACE_ID
        statement = (
            update(ScheduledTaskOccurrence).values(status="CANCELLED")
            if operation == "update"
            else delete(ScheduledTaskOccurrence)
        )
        result = session.execute(statement.where(ScheduledTaskOccurrence.id == key))
        assert result.rowcount == 0
    assert snapshot(factory, key) == before


@pytest.mark.parametrize("operation", ["dirty", "delete", "reassign"])
def test_preloaded_foreign_objects_cannot_be_written(isolated, operation):
    _, factory, _, _, occurrences, _ = isolated
    key = occurrences["other"]
    before = snapshot(factory, key)
    with factory() as session:
        row = session.get(ScheduledTaskOccurrence, key)
        session.info["workspace_id"] = LEGACY_WORKSPACE_ID
        if operation == "dirty":
            row.status = "CANCELLED"
        elif operation == "delete":
            session.delete(row)
        else:
            row.workspace_id = LEGACY_WORKSPACE_ID
        with pytest.raises(PermissionError):
            session.flush()
        session.rollback()
    assert snapshot(factory, key) == before


def test_workspace_models_cannot_be_omitted():
    assert set(workspace_models()) == {
        mapper.class_ for mapper in Base.registry.mappers if "workspace_id" in mapper.local_table.c
    }


def test_late_model_is_scoped_in_fresh_process():
    program = """
import uuid
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from packages.security.tenant import install_workspace_guards, workspace_models
from packages.database.base import Base
install_workspace_guards()
class LateResource(Base):
    __tablename__ = 'auth04_late_resource'
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column()
assert LateResource in workspace_models()
engine = create_engine('sqlite:///:memory:')
LateResource.__table__.create(engine)
own, other = uuid.uuid4(), uuid.uuid4()
with Session(engine) as session:
    session.add_all([LateResource(id=1, workspace_id=own), LateResource(id=2, workspace_id=other)])
    session.commit()
with Session(engine) as session:
    session.info['workspace_id'] = own
    assert session.scalars(select(LateResource.id)).all() == [1]
    assert session.get(LateResource, 2) is None
engine.dispose()
"""
    subprocess.run([sys.executable, "-c", program], check=True, timeout=30)


def test_missing_metadata_fails_closed(monkeypatch):
    class EmptyRegistry:
        mappers = ()

    monkeypatch.setattr(Base, "registry", EmptyRegistry())
    with pytest.raises(RuntimeError, match="metadata"):
        workspace_models()


@pytest.mark.parametrize("path", ["/api/v1/auth/login", "/api/v1/auth/me"])
def test_database_outage_is_controlled_and_observable(isolated, engine, caplog, monkeypatch, path):
    client, _, _, _, _, _ = isolated
    # In-process Alembic tests disable existing loggers; production migrations
    # run separately. Restore the app logger for this observability assertion.
    monkeypatch.setattr(logging.getLogger("apps.api.main"), "disabled", False)

    def outage(*args, **kwargs):
        raise OperationalError("disposable-secret-internal-marker", {}, Exception("outage"))

    event.listen(engine, "before_cursor_execute", outage)
    try:
        response = (
            client.post(path, json={"login": "auth04-viewer", "password": PASSWORD})
            if path.endswith("login")
            else client.get(path)
        )
    finally:
        event.remove(engine, "before_cursor_execute", outage)
    assert response.status_code == 503
    assert "Database unavailable" in caplog.text
    for secret in (PASSWORD, "disposable-secret-internal-marker", client.headers["Authorization"]):
        assert secret not in response.text + caplog.text
    assert "Traceback" not in response.text + caplog.text


def test_protected_router_mutations_have_explicit_permission():
    for path in Path("apps/api/routers").glob("*.py"):
        if path.name in {"identity.py", "native_auth.py"}:  # Dedicated identity/auth dependencies.
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prefix = ""
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "APIRouter"
            ):
                prefix = next((kw.value.value for kw in node.keywords if kw.arg == "prefix"), "")
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "router"
                and node.func.attr in {"post", "patch", "put", "delete"}
            ):
                route = "/api/v1" + prefix + node.args[0].value
                assert permission_for_request(node.func.attr.upper(), route) not in {
                    "workspace.read",
                    "unmapped.write",
                }, route


def seed_recovery(factory, jobs):
    ids = {}
    with factory.begin() as session:
        for label, job_id in jobs.items():
            job = session.get(ImportJob, job_id)
            job.status = "running"
            worker = WorkerInstance(
                worker_identifier=f"auth04b-{label}", status="busy", current_job_id=job_id
            )
            session.add(worker)
            session.flush()
            lease = JobLease(
                job_id=job_id,
                worker_id=worker.id,
                lease_token=f"disposable-{label}",
                acquired_at=utc_now() - timedelta(minutes=5),
                expires_at=utc_now() - timedelta(minutes=1),
            )
            session.add(lease)
            session.flush()
            ids[label] = (lease.id, worker.id)
    return ids


def recovery_snapshot(factory, job_id, ids):
    with factory() as session:
        return tuple(
            None if row is None else tuple(getattr(row, c.key) for c in row.__table__.columns)
            for row in (
                session.get(ImportJob, job_id),
                session.get(JobLease, ids[0]),
                session.get(WorkerInstance, ids[1]),
            )
        )


def test_parent_scoped_mixed_recovery(isolated):
    client, factory, actor, _, _, jobs = isolated
    set_role(factory, actor, "admin")
    ids = seed_recovery(factory, jobs)
    before = recovery_snapshot(factory, jobs["other"], ids["other"])
    result = client.post("/api/v1/operations/recover-abandoned")
    assert result.status_code == 200
    assert result.json() == {"recovered_job_ids": [str(jobs["own"])], "count": 1}
    assert recovery_snapshot(factory, jobs["other"], ids["other"]) == before
    with factory() as session:
        assert session.get(ImportJob, jobs["own"]).status == "retrying"
        assert session.get(JobLease, ids["own"][0]) is None
        assert session.get(WorkerInstance, ids["own"][1]).status == "unavailable"


def test_trusted_recovery_preserves_global_behavior(isolated):
    _, factory, _, _, _, jobs = isolated
    seed_recovery(factory, jobs)
    with factory.begin() as session:
        assert set(recover_abandoned_jobs(session)) == set(jobs.values())


def test_import_errors_follow_parent_even_with_known_foreign_id(isolated):
    client, factory, _, _, _, jobs = isolated
    with factory.begin() as session:
        for label, job_id in jobs.items():
            session.add(ImportError(job_id=job_id, error_code="TEST", message=f"private-{label}"))
    all_errors = client.get("/api/v1/import/errors")
    assert all_errors.status_code == 200
    assert all_errors.json()["meta"]["total"] == 1
    assert "private-own" in all_errors.text and "private-other" not in all_errors.text
    foreign = client.get("/api/v1/import/errors", params={"job_id": str(jobs["other"])})
    assert foreign.status_code == 200
    assert foreign.json()["items"] == [] and foreign.json()["meta"]["total"] == 0


def test_worker_listing_uses_current_job_parent(isolated):
    client, factory, _, _, _, jobs = isolated
    ids = seed_recovery(factory, jobs)
    response = client.get("/api/v1/operations/workers")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1
    assert [row["id"] for row in response.json()["items"]] == [str(ids["own"][1])]
    assert str(jobs["other"]) not in response.text


def test_old_lease_cannot_change_worker_now_serving_foreign_job(isolated):
    client, factory, actor, _, _, jobs = isolated
    set_role(factory, actor, "admin")
    ids = seed_recovery(factory, jobs)
    with factory.begin() as session:
        session.get(WorkerInstance, ids["own"][1]).current_job_id = jobs["other"]
    before = recovery_snapshot(factory, jobs["other"], ids["own"])[2]
    response = client.post("/api/v1/operations/recover-abandoned")
    assert response.status_code == 200
    assert recovery_snapshot(factory, jobs["other"], ids["own"])[2] == before


def test_concurrent_recovery_has_one_effect_and_preserves_foreign_state(isolated):
    client, factory, actor, _, _, jobs = isolated
    set_role(factory, actor, "admin")
    ids = seed_recovery(factory, jobs)
    before = recovery_snapshot(factory, jobs["other"], ids["other"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: client.post("/api/v1/operations/recover-abandoned"), range(2))
        )
    assert [r.status_code for r in responses] == [200, 200]
    assert sorted(r.json()["count"] for r in responses) == [0, 1]
    assert recovery_snapshot(factory, jobs["other"], ids["other"]) == before


@pytest.mark.parametrize("action", ["cancel", "restart", "retry"])
def test_admin_foreign_import_id_does_not_grant_mutation(isolated, action):
    client, factory, actor, _, _, jobs = isolated
    set_role(factory, actor, "admin")
    with factory() as session:
        job = session.get(ImportJob, jobs["other"])
        before = tuple(getattr(job, c.key) for c in job.__table__.columns)
    response = client.post(f"/api/v1/import/jobs/{jobs['other']}/{action}")
    assert response.status_code == 404
    with factory() as session:
        job = session.get(ImportJob, jobs["other"])
        assert tuple(getattr(job, c.key) for c in job.__table__.columns) == before


def test_foreign_paper_child_id_cannot_be_read_or_cancelled(isolated):
    client, factory, actor, _, _, jobs = isolated
    set_role(factory, actor, "admin")
    with factory.begin() as session:
        workspace = session.get(ImportJob, jobs["other"]).workspace_id
        portfolio = PaperPortfolio(
            workspace_id=workspace, name="foreign-plan", starting_cash=1000, cash_balance=1000
        )
        session.add(portfolio)
        session.flush()
        order = PaperOrder(
            portfolio_id=portfolio.id,
            asset_id=session.scalar(select(Asset.id)),
            client_order_id="foreign-order",
            side="buy",
            order_type="market",
            quantity=1,
            status="pending",
            assumptions={},
        )
        session.add(order)
        session.flush()
        portfolio_id, order_id = portfolio.id, order.id
    with factory() as session:
        before = tuple(
            getattr(session.get(PaperOrder, order_id), c.key) for c in PaperOrder.__table__.columns
        )
    for child in ("orders", "fills", "positions"):
        assert client.get(f"/api/v1/paper-portfolios/{portfolio_id}/{child}").status_code == 404
    assert (
        client.delete(f"/api/v1/paper-portfolios/{portfolio_id}/orders/{order_id}").status_code
        == 404
    )
    with factory() as session:
        assert (
            tuple(
                getattr(session.get(PaperOrder, order_id), c.key)
                for c in PaperOrder.__table__.columns
            )
            == before
        )


def test_native_admin_paper_preview_still_works(isolated):
    client, factory, actor, _, _, _ = isolated
    set_role(factory, actor, "admin")
    response = client.post(
        "/api/v1/paper/plans",
        json={
            "scores": {"A": 0.9},
            "domains": {"A": "tech"},
            "prices": {"A": 100},
            "equity": 1000,
        },
    )
    assert response.status_code == 200
    assert response.json()["brokerage_connectivity"] is False
