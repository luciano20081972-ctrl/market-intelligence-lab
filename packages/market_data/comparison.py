from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.time import utc_now
from packages.database.models import Asset, PriceBar, ProviderComparison


def _difference(left: Decimal, right: Decimal) -> Decimal:
    denominator = max(abs(left), abs(right), Decimal("0.000001"))
    return abs(left - right) / denominator


def compare_providers(
    session: Session,
    *,
    workspace_id: UUID,
    asset: Asset,
    primary_provider_id: UUID,
    secondary_provider_id: UUID,
    start_time: datetime,
    end_time: datetime,
    price_tolerance: Decimal = Decimal("0.001"),
    volume_tolerance: Decimal = Decimal("0.05"),
) -> ProviderComparison:
    if primary_provider_id == secondary_provider_id:
        raise ValueError("Two distinct providers are required")
    if start_time.tzinfo is None or end_time.tzinfo is None or start_time >= end_time:
        raise ValueError("Comparison dates must be timezone-aware and ordered")

    bars = session.scalars(
        select(PriceBar).where(
            PriceBar.asset_id == asset.id,
            PriceBar.provider_id.in_([primary_provider_id, secondary_provider_id]),
            PriceBar.event_time >= start_time,
            PriceBar.event_time <= end_time,
        )
    ).all()
    grouped: dict[UUID, dict[datetime, list[PriceBar]]] = {
        primary_provider_id: {},
        secondary_provider_id: {},
    }
    for bar in bars:
        provider_id = bar.provider_id
        if provider_id not in grouped:
            continue
        grouped[provider_id][bar.event_time] = [
            *grouped[provider_id].get(bar.event_time, []),
            bar,
        ]
    sessions = sorted(set(grouped[primary_provider_id]) | set(grouped[secondary_provider_id]))
    disagreements: list[dict[str, object]] = []
    agreed = 0
    within = 0
    for event_time in sessions:
        primary = grouped[primary_provider_id].get(event_time, [])
        secondary = grouped[secondary_provider_id].get(event_time, [])
        if len(primary) != 1 or len(secondary) != 1:
            disagreements.append(
                {
                    "session": event_time.isoformat(),
                    "type": "duplicate"
                    if len(primary) > 1 or len(secondary) > 1
                    else "missing_session",
                    "primary_count": len(primary),
                    "secondary_count": len(secondary),
                }
            )
            continue
        left, right = primary[0], secondary[0]
        differences = {
            field: str(_difference(getattr(left, field), getattr(right, field)))
            for field in ("open", "high", "low", "close")
        }
        volume_difference = _difference(Decimal(left.volume), Decimal(right.volume))
        adjustment_conflict = left.adjustment_status != right.adjustment_status
        price_conflict = any(Decimal(value) > price_tolerance for value in differences.values())
        volume_conflict = volume_difference > volume_tolerance
        checksum_change = left.checksum != right.checksum
        if price_conflict or volume_conflict or adjustment_conflict:
            disagreements.append(
                {
                    "session": event_time.isoformat(),
                    "type": "value_conflict",
                    "price_differences": differences,
                    "volume_difference": str(volume_difference),
                    "adjustment_state_difference": adjustment_conflict,
                    "checksum_difference": checksum_change,
                    "freshness_seconds": abs(
                        (left.retrieval_time - right.retrieval_time).total_seconds()
                    ),
                }
            )
        elif checksum_change or any(Decimal(value) > 0 for value in differences.values()):
            within += 1
        else:
            agreed += 1
    status = "conflict" if disagreements else "within_tolerance" if within else "agreed"
    comparison = ProviderComparison(
        workspace_id=workspace_id,
        asset_id=asset.id,
        primary_provider_id=primary_provider_id,
        secondary_provider_id=secondary_provider_id,
        start_time=start_time,
        end_time=end_time,
        tolerance_configuration={
            "price_relative": str(price_tolerance),
            "volume_relative": str(volume_tolerance),
        },
        summary={
            "sessions": len(sessions),
            "exact_agreement": agreed,
            "within_tolerance": within,
            "conflicts": len(disagreements),
            "session_coverage_agreement": str(
                Decimal(len(sessions) - sum(d["type"] == "missing_session" for d in disagreements))
                / Decimal(max(len(sessions), 1))
            ),
            "corporate_action_comparison": "not_available",
        },
        disagreements=disagreements,
        resolution_status=status,
        compared_at=utc_now(),
    )
    session.add(comparison)
    session.flush()
    return comparison
