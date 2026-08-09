from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from packages.compute.types import JobClass, ResourceEstimate


@dataclass(frozen=True)
class ResourceSnapshot:
    available_ram_mb: int
    load_1m: float
    cpu_count: int
    running_analytical_jobs: int = 0

    @property
    def load_per_cpu(self) -> float:
        return self.load_1m / max(self.cpu_count, 1)


@dataclass(frozen=True)
class ResourceDecision:
    allowed: bool
    reason: str


class LocalResourceGuard:
    def __init__(
        self,
        *,
        min_available_ram_mb: int = 1536,
        max_load_per_cpu: float = 1.25,
        max_running_jobs: int = 1,
        heavy_concurrency: int = 0,
        reserve_ram_mb: int = 1024,
    ) -> None:
        self.min_available_ram_mb = min_available_ram_mb
        self.max_load_per_cpu = max_load_per_cpu
        self.max_running_jobs = max_running_jobs
        self.heavy_concurrency = heavy_concurrency
        self.reserve_ram_mb = reserve_ram_mb

    def snapshot(self) -> ResourceSnapshot:
        available_kb = 0
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                available_kb = int(line.split()[1])
                break
        return ResourceSnapshot(
            available_ram_mb=available_kb // 1024,
            load_1m=os.getloadavg()[0],
            cpu_count=os.cpu_count() or 1,
        )

    def evaluate(
        self,
        job_class: JobClass,
        estimate: ResourceEstimate,
        snapshot: ResourceSnapshot,
    ) -> ResourceDecision:
        if job_class in {JobClass.HEAVY, JobClass.VERY_HEAVY} and self.heavy_concurrency == 0:
            return ResourceDecision(False, "heavy_local_execution_disabled")
        if snapshot.running_analytical_jobs >= self.max_running_jobs:
            return ResourceDecision(False, "local_concurrency_limit")
        if snapshot.available_ram_mb < self.min_available_ram_mb:
            return ResourceDecision(False, "host_memory_floor")
        if estimate.ram_mb + self.reserve_ram_mb > snapshot.available_ram_mb:
            return ResourceDecision(False, "estimated_memory_exceeds_safe_capacity")
        if snapshot.load_per_cpu > self.max_load_per_cpu:
            return ResourceDecision(False, "host_load_limit")
        return ResourceDecision(True, "local_capacity_available")
