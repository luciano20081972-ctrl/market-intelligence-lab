from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from packages.market_data.adapters import (
    PROVIDER_DEFINITIONS,
    DisabledProviderAdapter,
    SyntheticHistoricalAdapter,
)
from packages.market_data.types import MarketDataAdapter


@dataclass(frozen=True)
class RegisteredProvider:
    code: str
    name: str
    adapter: MarketDataAdapter
    enabled_by_default: bool
    credential_environment_keys: tuple[str, ...]


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, RegisteredProvider] = {}

    def register(
        self,
        adapter: MarketDataAdapter,
        *,
        enabled_by_default: bool = False,
        credential_environment_keys: tuple[str, ...] = (),
    ) -> None:
        code = adapter.code.strip().lower()
        if not code:
            raise ValueError("provider code cannot be blank")
        if code in self._providers:
            raise ValueError(f"provider '{code}' is already registered")
        self._providers[code] = RegisteredProvider(
            code=code,
            name=adapter.name,
            adapter=adapter,
            enabled_by_default=enabled_by_default,
            credential_environment_keys=credential_environment_keys,
        )

    def get(self, code: str) -> RegisteredProvider:
        normalized = code.strip().lower()
        try:
            return self._providers[normalized]
        except KeyError as exc:
            raise ValueError(f"unknown provider '{normalized}'") from exc

    def all(self) -> list[RegisteredProvider]:
        return sorted(self._providers.values(), key=lambda item: item.name)


def build_default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(SyntheticHistoricalAdapter(), enabled_by_default=True)
    for definition in PROVIDER_DEFINITIONS:
        code = str(definition["code"])
        name = str(definition["name"])
        environment_keys = tuple(cast(list[str], definition["env"]))
        registry.register(
            DisabledProviderAdapter(code, name),
            enabled_by_default=False,
            credential_environment_keys=environment_keys,
        )
    return registry


default_registry = build_default_registry()
