from __future__ import annotations

from typing import Any

FORBIDDEN_EXECUTION_FIELDS = {
    "brokerage_credentials",
    "brokerage_account",
    "real_order",
    "live_order",
    "fidelity",
    "margin",
    "withdrawal",
    "deposit",
}


def assert_research_or_paper_only(payload: dict[str, Any]) -> None:
    keys: set[str] = set()
    modes: list[str] = []

    def inspect(value: Any) -> None:
        if isinstance(value, dict):
            for raw_key, child in value.items():
                key = str(raw_key).lower()
                keys.add(key)
                if key in {"execution_mode", "mode"}:
                    modes.append(str(child).lower())
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    inspect(payload)
    blocked = sorted(keys & FORBIDDEN_EXECUTION_FIELDS)
    if blocked:
        raise ValueError(f"real brokerage execution is forbidden: {', '.join(blocked)}")
    allowed = {"paper", "simulated", "hypothetical", "research", "dry_run"}
    if any(mode not in allowed for mode in modes):
        raise ValueError(
            "execution mode must remain paper, simulated, hypothetical, research, or dry_run"
        )
