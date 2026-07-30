from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from packages.auth.service import AuthError, SupabaseJwtVerifier
from packages.core.config import Settings
from packages.database.models import (
    LEGACY_USER_ID,
    LEGACY_WORKSPACE_ID,
    Asset,
    DataSource,
    PriceBar,
    Provider,
    UserProfile,
    WorkspaceMembership,
)
from packages.database.session import make_session_factory, session_scope
from packages.infrastructure import load_service_registry
from packages.market_data.adapters import TwelveDataAdapter
from packages.market_data.comparison import compare_providers
from packages.market_data.types import (
    ProviderAccessDeniedError,
    ProviderNoDataError,
    ProviderRateLimitError,
    ProviderSchemaError,
)


def _claims(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    value: dict[str, object] = {
        "sub": str(uuid.uuid4()),
        "email": "researcher@example.test",
        "email_verified": True,
        "iss": "https://project.supabase.co/auth/v1",
        "aud": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    "override",
    [
        {"exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())},
        {"iss": "https://attacker.invalid/auth/v1"},
        {"aud": "wrong-audience"},
    ],
)
def test_supabase_jwt_claims_fail_closed(override: dict[str, object]) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = SupabaseJwtVerifier(
        Settings(auth_mode="supabase", supabase_url="https://project.supabase.co")
    )
    verifier._jwks = SimpleNamespace(  # type: ignore[assignment]
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=private_key.public_key())
    )
    token = jwt.encode(_claims(**override), private_key, algorithm="RS256")
    with pytest.raises(AuthError, match="invalid or expired"):
        verifier.verify(token)


def test_supabase_jwt_valid_signature_and_subject() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = str(uuid.uuid4())
    verifier = SupabaseJwtVerifier(
        Settings(auth_mode="supabase", supabase_url="https://project.supabase.co")
    )
    verifier._jwks = SimpleNamespace(  # type: ignore[assignment]
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=private_key.public_key())
    )
    principal = verifier.verify(jwt.encode(_claims(sub=subject), private_key, algorithm="RS256"))
    assert principal.user_id == uuid.UUID(subject)
    assert principal.email_verified is True


def test_production_refuses_disabled_authentication() -> None:
    with pytest.raises(ValidationError, match="forbidden in production"):
        Settings(environment="production", auth_mode="disabled")


def test_development_identity_and_workspace_isolation(client: TestClient) -> None:
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["provider"] == "development"
    created = client.post("/api/v1/workspaces", json={"name": "Workspace B", "slug": "workspace-b"})
    assert created.status_code == 201
    workspace_b = created.json()["id"]
    first = client.post("/api/v1/watchlists", json={"name": "Workspace A Only"})
    second = client.post(
        "/api/v1/watchlists",
        headers={"X-Workspace-ID": workspace_b},
        json={"name": "Workspace B Only"},
    )
    assert first.status_code == second.status_code == 201
    names_a = {item["name"] for item in client.get("/api/v1/watchlists").json()}
    names_b = {
        item["name"]
        for item in client.get("/api/v1/watchlists", headers={"X-Workspace-ID": workspace_b}).json()
    }
    assert "Workspace A Only" in names_a and "Workspace B Only" not in names_a
    assert "Workspace B Only" in names_b and "Workspace A Only" not in names_b
    guessed = client.get(f"/api/v1/watchlists/{second.json()['id']}")
    assert guessed.status_code == 404


def test_auth_health_and_safe_event_audit(client: TestClient) -> None:
    health = client.get("/api/v1/auth/health")
    assert health.json() == {
        "status": "healthy",
        "mode": "disabled",
        "provider_configured": True,
    }
    event = client.post(
        "/api/v1/auth/events",
        json={"action": "auth.password_reset_requested", "result": "success"},
    )
    assert event.status_code == 202 and event.json()["recorded"] is True


def test_viewer_cannot_mutate_workspace(client: TestClient, engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        membership = session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == LEGACY_USER_ID,
                WorkspaceMembership.workspace_id == LEGACY_WORKSPACE_ID,
            )
        )
        assert membership is not None
        membership.role = "viewer"
    response = client.post("/api/v1/watchlists", json={"name": "Forbidden"})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def _twelve_transport(payload: object, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.twelvedata.com"
        assert request.headers["Authorization"] == "apikey fixture-key"
        return httpx.Response(
            status,
            headers={"content-type": "application/json"},
            content=json.dumps(payload).encode(),
            request=request,
        )

    return httpx.MockTransport(handler)


def test_twelve_data_fixture_parsing_and_provenance() -> None:
    adapter = TwelveDataAdapter(
        "fixture-key",
        transport=_twelve_transport(
            {
                "status": "ok",
                "values": [
                    {
                        "datetime": "2026-07-06",
                        "open": "100",
                        "high": "105",
                        "low": "99",
                        "close": "104",
                        "volume": "12345",
                    }
                ],
            }
        ),
    )
    bars = adapter.fetch_historical_bars(
        "aapl", datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 7, 10, tzinfo=UTC)
    )
    assert bars[0].symbol == "AAPL"
    assert bars[0].checksum and bars[0].provider_symbol == "AAPL"
    assert bars[0].adjustment_status == "provider_adjusted"


@pytest.mark.parametrize(
    ("payload", "status", "error"),
    [
        ({"status": "error", "code": 401}, 200, ProviderAccessDeniedError),
        ({"status": "error", "code": 429}, 200, ProviderRateLimitError),
        ({"status": "ok", "values": []}, 200, ProviderNoDataError),
        ({"status": "ok", "values": [{"datetime": "2026-07-06"}]}, 200, ProviderSchemaError),
    ],
)
def test_twelve_data_safe_error_classification(
    payload: object, status: int, error: type[Exception]
) -> None:
    adapter = TwelveDataAdapter("fixture-key", transport=_twelve_transport(payload, status))
    with pytest.raises(error):
        adapter.fetch_historical_bars(
            "AAPL", datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 7, 10, tzinfo=UTC)
        )


@pytest.mark.live_provider
def test_twelve_data_optional_live_smoke() -> None:
    if os.getenv("MIL_RUN_LIVE_TWELVE_DATA_TESTS") != "true":
        pytest.skip("set MIL_RUN_LIVE_TWELVE_DATA_TESTS=true for one bounded live request")
    key = os.getenv("MIL_TWELVE_DATA_API_KEY")
    if not key:
        pytest.skip("MIL_TWELVE_DATA_API_KEY is not configured")
    bars = TwelveDataAdapter(key).fetch_historical_bars(
        "AAPL", datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 7, 3, tzinfo=UTC)
    )
    assert bars and all(bar.symbol == "AAPL" for bar in bars)


def test_provider_comparison_records_conflict(engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        session.info["workspace_id"] = LEGACY_WORKSPACE_ID
        asset = session.scalar(select(Asset).where(Asset.symbol == "AAPL"))
        primary = session.scalar(select(Provider).where(Provider.code == "synthetic"))
        secondary = session.scalar(select(Provider).where(Provider.code == "twelve_data"))
        bar = session.scalar(select(PriceBar).where(PriceBar.asset_id == asset.id))  # type: ignore[union-attr]
        assert asset and primary and secondary and bar
        source = DataSource(
            name="Twelve Data fixture source",
            provider_type="twelve_data",
            is_enabled=True,
            health="fixture_tested",
            license_notes="No redistribution rights claimed.",
        )
        session.add(source)
        session.flush()
        session.add(
            PriceBar(
                asset_id=asset.id,
                interval=bar.interval,
                event_time=bar.event_time,
                publication_time=bar.publication_time,
                effective_time=bar.effective_time,
                retrieval_time=bar.retrieval_time + timedelta(minutes=1),
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close * Decimal("1.02"),
                adjusted_close=bar.adjusted_close,
                volume=bar.volume * 2,
                data_source_id=source.id,
                provider_id=secondary.id,
                checksum="f" * 64,
                adjustment_status="provider_adjusted",
                is_demonstration_data=False,
            )
        )
        session.flush()
        comparison = compare_providers(
            session,
            workspace_id=LEGACY_WORKSPACE_ID,
            asset=asset,
            primary_provider_id=primary.id,
            secondary_provider_id=secondary.id,
            start_time=bar.event_time - timedelta(minutes=1),
            end_time=bar.event_time + timedelta(minutes=1),
        )
        assert comparison.resolution_status == "conflict"
        assert comparison.disagreements[0]["type"] == "value_conflict"


def test_manifest_validation_and_audit_endpoints(client: TestClient) -> None:
    strategies = client.get("/api/v1/strategies").json()["items"]
    version_id = next(
        item["latest_version"]["id"]
        for item in strategies
        if item["strategy_type"] == "buy_and_hold"
    )
    response = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": version_id,
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "start_time": "2025-01-02T21:00:00Z",
            "end_time": "2025-06-18T21:00:00Z",
            "initial_cash": "100000",
            "commission": "1",
            "spread_bps": "2",
            "slippage_bps": "1",
            "execution_delay": 1,
            "max_position_pct": "0.50",
            "max_total_exposure": "1.00",
        },
    )
    assert response.status_code == 201
    run_id = response.json()["id"]
    manifest = client.get(f"/api/v1/backtests/{run_id}/manifest").json()
    report = client.get(f"/api/v1/backtests/{run_id}/validation-report").json()
    audit = client.get(f"/api/v1/workspaces/{LEGACY_WORKSPACE_ID}/audit-events").json()
    assert manifest["status"] == "available" and len(manifest["checksum"]) == 64
    assert report["overall_status"] == "failed"
    assert report["is_validated"] is False
    assert any(
        rule["name"] == "publication_time_leakage" and rule["status"] == "failed"
        for rule in report["rules"]
    )
    assert any(item["action"] == "backtest.completed" for item in audit["items"])


def test_infrastructure_registry_is_safe_and_exposed(client: TestClient) -> None:
    registry = load_service_registry()
    assert len(registry) == 7
    assert {item["service_name"] for item in registry} == {
        "GitHub",
        "Supabase",
        "Cloudflare",
        "Sentry",
        "Better Stack",
        "Codecov",
        "Resend",
    }
    response = client.get("/api/v1/operations/infrastructure-services")
    assert response.status_code == 200
    assert response.json()["contains_secrets"] is False
    serialized = json.dumps(response.json()).lower()
    assert "service_role" not in serialized and "fixture-key" not in serialized


def test_disabled_profile_is_rejected(client: TestClient, engine: object) -> None:
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        profile = session.get(UserProfile, LEGACY_USER_ID)
        assert profile is not None
        profile.is_disabled = True
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "user_disabled"
