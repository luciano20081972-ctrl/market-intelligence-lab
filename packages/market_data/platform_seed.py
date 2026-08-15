from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import ExchangeCalendar, Provider, ProviderCredential
from packages.market_data.calendars import XNYS_HOLIDAYS, generate_maintained_sessions
from packages.market_data.registry import default_registry

PLATFORM_NAMESPACE = uuid.UUID("b5437530-e21b-4bb1-99a7-1c522be8b0ec")


def provider_id(code: str) -> uuid.UUID:
    return uuid.uuid5(PLATFORM_NAMESPACE, f"provider:{code}")


def seed_market_data_platform(
    session: Session,
    *,
    calendar_start: date = date(2020, 1, 1),
    calendar_end: date = date(2035, 12, 31),
) -> dict[str, int]:
    inserted_providers = 0
    inserted_credentials = 0
    for registered in default_registry.all():
        provider = session.scalar(select(Provider).where(Provider.code == registered.code))
        if provider is None:
            provider = Provider(
                id=provider_id(registered.code),
                code=registered.code,
                name=registered.name,
                adapter_type=type(registered.adapter).__name__,
                capabilities=list(registered.adapter.capabilities),
                configuration={"network_enabled": False},
                credential_environment_keys=list(registered.credential_environment_keys),
                is_enabled=registered.enabled_by_default,
                health=(
                    "healthy"
                    if registered.code == "synthetic"
                    else "unknown"
                    if registered.enabled_by_default
                    else "disabled"
                ),
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
                updated_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
            session.add(provider)
            session.flush()
            inserted_providers += 1
        else:
            # Reconcile safe registry metadata on upgrades without replacing the
            # provider row or its operational history.
            provider.name = registered.name
            provider.adapter_type = type(registered.adapter).__name__
            provider.capabilities = list(registered.adapter.capabilities)
            provider.credential_environment_keys = list(registered.credential_environment_keys)
        if registered.code == "stooq":
            provider.configuration = {
                "network_enabled": True,
                "base_url": "https://stooq.com/q/d/l/",
                "authentication_required": False,
                "commercial_redistribution_licensed": False,
            }
            provider.is_enabled = True
            if provider.health == "disabled":
                provider.health = "unknown"
        if registered.code == "twelve_data":
            configured = bool(os.getenv("MIL_TWELVE_DATA_API_KEY"))
            provider.adapter_type = type(registered.adapter).__name__
            provider.capabilities = list(registered.adapter.capabilities)
            provider.configuration = {
                "network_enabled": configured,
                "base_url": "https://api.twelvedata.com",
                "authentication_required": True,
                "commercial_redistribution_licensed": False,
                "live_verified": False,
            }
            provider.is_enabled = configured
            provider.health = "unknown" if configured else "unconfigured"
        for environment_key in registered.credential_environment_keys:
            exists = session.scalar(
                select(ProviderCredential).where(
                    ProviderCredential.provider_id == provider.id,
                    ProviderCredential.key_name == environment_key,
                )
            )
            if exists is None:
                session.add(
                    ProviderCredential(
                        provider_id=provider.id,
                        key_name=environment_key,
                        secret_reference=f"environment:{environment_key}",
                        is_configured=bool(os.getenv(environment_key)),
                    )
                )
                inserted_credentials += 1
            else:
                exists.is_configured = bool(os.getenv(environment_key))

    calendar = session.scalar(select(ExchangeCalendar).where(ExchangeCalendar.code == "XNYS"))
    if calendar is None:
        calendar = ExchangeCalendar(
            id=uuid.uuid5(PLATFORM_NAMESPACE, "calendar:XNYS"),
            code="XNYS",
            name="New York Stock Exchange",
            timezone="America/New_York",
            weekend_days=[5, 6],
            holiday_dates=sorted(XNYS_HOLIDAYS),
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        session.add(calendar)
        session.flush()
    inserted_sessions = generate_maintained_sessions(
        session,
        calendar,
        calendar_start,
        calendar_end,
    )
    return {
        "providers_inserted": inserted_providers,
        "credentials_inserted": inserted_credentials,
        "sessions_inserted": inserted_sessions,
    }
