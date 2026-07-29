from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import ExchangeCalendar, Provider, ProviderCredential
from packages.market_data.calendars import XNYS_EARLY_CLOSES, XNYS_HOLIDAYS, generate_sessions
from packages.market_data.registry import default_registry

PLATFORM_NAMESPACE = uuid.UUID("b5437530-e21b-4bb1-99a7-1c522be8b0ec")


def provider_id(code: str) -> uuid.UUID:
    return uuid.uuid5(PLATFORM_NAMESPACE, f"provider:{code}")


def seed_market_data_platform(session: Session) -> dict[str, int]:
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
                health="healthy" if registered.enabled_by_default else "disabled",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
                updated_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
            session.add(provider)
            session.flush()
            inserted_providers += 1
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
                        is_configured=False,
                    )
                )
                inserted_credentials += 1

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
    inserted_sessions = generate_sessions(
        session,
        calendar,
        date(2025, 1, 1),
        date(2027, 12, 31),
        early_closes=XNYS_EARLY_CLOSES,
    )
    return {
        "providers_inserted": inserted_providers,
        "credentials_inserted": inserted_credentials,
        "sessions_inserted": inserted_sessions,
    }
