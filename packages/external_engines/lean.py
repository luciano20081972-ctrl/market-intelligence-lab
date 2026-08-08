from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.upstream.protocols import (
    UpstreamCapability,
    UpstreamHealthReport,
    UpstreamVersionInfo,
)


@dataclass(frozen=True)
class LeanBacktestRequest:
    strategy: str
    symbols: tuple[str, ...]
    start: date
    end: date
    initial_cash: Decimal
    fee_per_order: Decimal
    slippage_bps: Decimal
    live_mode: bool = False

    def validate(self) -> None:
        if self.live_mode:
            raise ValueError("LEAN live-trading mode is forbidden")
        if self.strategy not in {"buy_and_hold", "moving_average_crossover"}:
            raise ValueError("Only deterministic reference strategies are allowed")
        if not 1 <= len(self.symbols) <= 2:
            raise ValueError("One or two assets are required")
        if any(not symbol.isalnum() or len(symbol) > 16 for symbol in self.symbols):
            raise ValueError("Algorithm symbols are invalid")
        if self.end <= self.start or self.initial_cash <= 0:
            raise ValueError("Backtest dates and initial cash are invalid")
        if self.fee_per_order < 0 or self.slippage_bps < 0:
            raise ValueError("Fees and slippage cannot be negative")


class LeanAdapter:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable

    def _resolved(self) -> str | None:
        if self.executable:
            candidate = Path(self.executable)
            return str(candidate) if candidate.is_file() else None
        return shutil.which("lean")

    def health(self) -> UpstreamHealthReport:
        available = self._resolved() is not None
        return UpstreamHealthReport(
            status="disabled" if not available else "available_disabled_by_default",
            available=available,
            capabilities=(
                UpstreamCapability(
                    "fixture_backtest", "Deterministic result-package parsing", True
                ),
                UpstreamCapability("isolated_process", "Bounded external runner", False),
            ),
            version=UpstreamVersionInfo(
                "QuantConnect/Lean",
                "prototype-1",
                None,
                "962fcd6b58a56d7a52cf7178a42b965ff3681115",
            ),
            message=(
                "LEAN is installed but execution remains disabled by default"
                if available
                else "LEAN is optional and unavailable; core functionality is unaffected"
            ),
        )

    def fixture_run(self, request: LeanBacktestRequest) -> dict[str, Any]:
        request.validate()
        serialized = json.dumps(asdict(request), default=str, sort_keys=True)
        request_checksum = hashlib.sha256(serialized.encode()).hexdigest()
        result = {
            "orders": 1,
            "fills": 1,
            "ending_equity": "10342.50",
            "maximum_drawdown": "-0.0321",
            "trades": 1,
            "fees": str(request.fee_per_order),
            "timestamps": [f"{request.start.isoformat()}T21:00:00+00:00"],
            "equity_curve": [
                {"date": request.start.isoformat(), "equity": str(request.initial_cash)},
                {"date": request.end.isoformat(), "equity": "10342.50"},
            ],
        }
        return {
            "status": "fixture_completed",
            "request_checksum": request_checksum,
            "result": result,
            "manifest": {
                "engine": "QuantConnect/Lean",
                "engine_commit": self.health().version.source_commit,
                "adapter_version": "prototype-1",
                "deterministic": True,
                "live_mode": False,
                "brokerage_credentials": False,
                "timeout_seconds": 60,
                "resource_limits": {"cpu": 1, "memory_mb": 1024},
            },
            "comparison": {
                "internal_ending_equity": "10340.00",
                "lean_ending_equity": "10342.50",
                "difference": "2.50",
                "explanation": (
                    "Fixture demonstrates normalized comparison; fill timing may differ."
                ),
            },
        }

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("External LEAN process execution is disabled by default")
