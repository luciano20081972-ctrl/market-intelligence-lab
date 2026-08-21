from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from statistics import pstdev
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.time import utc_now
from packages.database.models import (
    Asset,
    AssetCapability,
    AssetListing,
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
    PriceBar,
    UniverseLayerMembership,
    UniverseSelectionRun,
    Watchlist,
    WatchlistAsset,
)

LAYERS = (
    "US_ELIGIBLE",
    "REFERENCE_READY",
    "HISTORICAL_READY",
    "SCREENING",
    "CANDIDATE",
    "ACTIVE_INTELLIGENCE",
    "REALTIME",
)


def _score(rows: list[PriceBar]) -> tuple[float, dict[str, float]]:
    ordered = sorted(rows, key=lambda row: row.event_time)[-30:]
    if len(ordered) < 2:
        return 0.0, {"data_completeness": len(ordered) / 30}
    closes = [float(row.close) for row in ordered]
    volumes = [float(row.volume) for row in ordered]
    returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
    dollar_volume = sum(
        price * volume for price, volume in zip(closes, volumes, strict=True)
    ) / len(closes)
    recent_return = closes[-1] / closes[max(0, len(closes) - 6)] - 1
    gap = abs(float(ordered[-1].open) / closes[-2] - 1)
    average_volume = sum(volumes[:-1]) / max(len(volumes) - 1, 1)
    volume_anomaly = volumes[-1] / average_volume if average_volume else 0.0
    volatility = pstdev(returns) if len(returns) > 1 else 0.0
    momentum = closes[-1] / closes[0] - 1
    completeness = min(len(ordered) / 20, 1.0)
    components = {
        "liquidity": math.log10(max(dollar_volume, 1.0)),
        "dollar_volume": dollar_volume,
        "recent_return": recent_return,
        "price_gap": gap,
        "volume_anomaly": volume_anomaly,
        "realized_volatility": volatility,
        "relative_strength": recent_return,
        "momentum": momentum,
        "data_completeness": completeness,
    }
    score = (
        components["liquidity"] * 0.35
        + abs(recent_return) * 15
        + min(volume_anomaly, 5) * 0.15
        + volatility * 8
        + momentum * 2
        + completeness
    )
    return score, components


def select_dynamic_universe(
    session: Session,
    *,
    workspace_id: UUID | None,
    realtime_capacity: int,
    candidate_capacity: int = 100,
    active_capacity: int = 200,
    provider_code: str = "alpaca",
    effective_at: datetime | None = None,
) -> UniverseSelectionRun:
    """Persist a deterministic, explainable layered universe from stored data only."""
    if min(realtime_capacity, candidate_capacity, active_capacity) < 0:
        raise ValueError("Universe capacities cannot be negative")
    now = effective_at or utc_now()
    eligible = session.scalars(
        select(Asset)
        .join(AssetListing, AssetListing.asset_id == Asset.id)
        .where(
            Asset.is_active.is_(True),
            AssetListing.is_active.is_(True),
            AssetListing.eligibility_status == "ELIGIBLE",
            AssetListing.valid_to.is_(None),
        )
        .order_by(Asset.symbol)
    ).unique().all()
    eligible_ids = {asset.id for asset in eligible}
    reference_ready = {
        asset_id
        for asset_id in session.scalars(
            select(AssetCapability.asset_id).where(
                AssetCapability.asset_id.in_(eligible_ids),
                AssetCapability.capability == "REFERENCE",
                AssetCapability.status == "REFERENCE_AVAILABLE",
            )
        )
    } if eligible_ids else set()
    bars_by_asset: dict[UUID, list[PriceBar]] = defaultdict(list)
    if eligible_ids:
        for bar in session.scalars(
            select(PriceBar)
            .where(PriceBar.asset_id.in_(eligible_ids), PriceBar.is_demonstration_data.is_(False))
            .order_by(PriceBar.asset_id, PriceBar.event_time.desc())
        ):
            if len(bars_by_asset[bar.asset_id]) < 30:
                bars_by_asset[bar.asset_id].append(bar)
    scored = [
        (asset.id, *_score(bars_by_asset.get(asset.id, [])))
        for asset in eligible
        if bars_by_asset.get(asset.id)
    ]
    scored.sort(key=lambda item: (-item[1], str(item[0])))
    candidates = scored[:candidate_capacity]
    promoted: dict[UUID, set[str]] = defaultdict(set)
    if workspace_id is not None:
        watchlist_ids = select(Watchlist.id).where(Watchlist.workspace_id == workspace_id)
        for asset_id in session.scalars(
            select(WatchlistAsset.asset_id).where(WatchlistAsset.watchlist_id.in_(watchlist_ids))
        ):
            promoted[asset_id].add("WATCHLIST")
        for asset_id in session.scalars(
            select(PaperPosition.asset_id)
            .join(PaperPortfolio, PaperPosition.portfolio_id == PaperPortfolio.id)
            .where(
                PaperPortfolio.workspace_id == workspace_id,
                PaperPosition.quantity > 0,
            )
        ):
            promoted[asset_id].add("PAPER_HOLDING")
        for asset_id in session.scalars(
            select(PaperOrder.asset_id)
            .join(PaperPortfolio, PaperOrder.portfolio_id == PaperPortfolio.id)
            .where(
                PaperPortfolio.workspace_id == workspace_id,
                PaperOrder.status.in_(("open", "pending", "accepted")),
            )
        ):
            promoted[asset_id].add("OPEN_PAPER_ORDER")
    for asset_id, _value, _components in candidates:
        promoted[asset_id].add("RANKED_CANDIDATE")
    ranked_ids = [item[0] for item in candidates]
    active_ids = sorted(promoted, key=lambda value: (value not in ranked_ids, str(value)))
    active_ids = active_ids[:active_capacity]
    realtime_ids = active_ids[:realtime_capacity]
    checksum_payload = {
        "policy": "v0.15.0",
        "workspace": str(workspace_id) if workspace_id else None,
        "eligible": [str(asset.id) for asset in eligible],
        "active": [str(value) for value in active_ids],
        "realtime": [str(value) for value in realtime_ids],
        "effective_at": now.isoformat(),
    }
    checksum = hashlib.sha256(
        json.dumps(checksum_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    run = UniverseSelectionRun(
        workspace_id=workspace_id,
        effective_at=now,
        policy_version="v0.15.0",
        provider_code=provider_code,
        realtime_capacity=realtime_capacity,
        input_asset_count=len(eligible),
        candidate_count=len(candidates),
        active_count=len(active_ids),
        realtime_count=len(realtime_ids),
        status="SUCCEEDED",
        checksum=checksum,
        summary={"layers": list(LAYERS), "synthetic_bars_excluded": True},
    )
    session.add(run)
    session.flush()
    previous = session.scalars(
        select(UniverseLayerMembership).where(
            UniverseLayerMembership.workspace_id == workspace_id,
            UniverseLayerMembership.effective_to.is_(None),
        )
    )
    for membership in previous:
        membership.effective_to = now
    layer_assets: dict[str, list[UUID]] = {
        "US_ELIGIBLE": [asset.id for asset in eligible],
        "REFERENCE_READY": sorted(reference_ready, key=str),
        "HISTORICAL_READY": sorted(bars_by_asset, key=str),
        "SCREENING": [item[0] for item in scored],
        "CANDIDATE": ranked_ids,
        "ACTIVE_INTELLIGENCE": active_ids,
        "REALTIME": realtime_ids,
    }
    score_lookup = {asset_id: (value, components) for asset_id, value, components in scored}
    for layer, asset_ids in layer_assets.items():
        for rank, asset_id in enumerate(asset_ids, 1):
            value, components = score_lookup.get(asset_id, (None, {}))
            reasons = sorted(promoted.get(asset_id, {layer})) if layer in {
                "ACTIVE_INTELLIGENCE", "REALTIME"
            } else [layer]
            session.add(
                UniverseLayerMembership(
                    selection_run_id=run.id,
                    workspace_id=workspace_id,
                    asset_id=asset_id,
                    layer=layer,
                    rank=rank,
                    score=Decimal(str(round(value, 8))) if value is not None else None,
                    score_components=components,
                    reason_codes=reasons,
                    effective_from=now,
                )
            )
    session.flush()
    return run
