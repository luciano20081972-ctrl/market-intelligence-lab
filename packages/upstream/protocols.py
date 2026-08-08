from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class UpstreamCapability:
    code: str
    description: str
    fixture_tested: bool
    live_verified: bool = False


@dataclass(frozen=True)
class UpstreamVersionInfo:
    project: str
    adapter_version: str
    library_version: str | None
    source_commit: str | None


@dataclass(frozen=True)
class UpstreamHealthReport:
    status: str
    available: bool
    capabilities: tuple[UpstreamCapability, ...]
    version: UpstreamVersionInfo
    message: str


class SecFilingsProvider(Protocol):
    def health(self) -> UpstreamHealthReport: ...

    def import_company(self, cik: str, forms: tuple[str, ...]) -> dict[str, Any]: ...


class PortfolioAnalyticsEngine(Protocol):
    def health(self) -> UpstreamHealthReport: ...

    def calculate(
        self, returns: tuple[float, ...], benchmark: tuple[float, ...] | None = None
    ) -> dict[str, float | None]: ...


class PortfolioOptimizer(Protocol):
    def health(self) -> UpstreamHealthReport: ...

    def optimize(
        self,
        returns: dict[str, tuple[float, ...]],
        *,
        model: str,
        allow_short: bool = False,
        allow_leverage: bool = False,
    ) -> dict[str, Any]: ...


class ExternalBacktestEngine(Protocol):
    def health(self) -> UpstreamHealthReport: ...

    def run(self, request: dict[str, Any]) -> dict[str, Any]: ...
