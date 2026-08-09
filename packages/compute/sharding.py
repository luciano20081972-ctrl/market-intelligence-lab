from __future__ import annotations

from collections.abc import Callable, Iterable

from packages.compute.manifests import canonical_checksum


def deterministic_shards[T](items: Iterable[T], task_count: int) -> list[list[T]]:
    if task_count < 1:
        raise ValueError("task_count must be positive")
    ordered = sorted(items, key=canonical_checksum)
    shards: list[list[T]] = [[] for _ in range(task_count)]
    for index, item in enumerate(ordered):
        shards[index % task_count].append(item)
    return shards


def deterministic_merge[T](
    partitions: Iterable[tuple[int, Iterable[T]]],
    *,
    task_count: int,
    identity: Callable[[T], str],
) -> list[T]:
    collected = list(partitions)
    indexes = [index for index, _ in collected]
    if sorted(indexes) != list(range(task_count)):
        raise ValueError("partitions must be complete and unique")
    merged: dict[str, T] = {}
    for _, items in sorted(collected):
        for item in items:
            key = identity(item)
            if key in merged:
                raise ValueError(f"duplicate result identity: {key}")
            merged[key] = item
    return [merged[key] for key in sorted(merged)]
