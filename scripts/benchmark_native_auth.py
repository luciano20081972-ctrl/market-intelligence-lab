"""Bounded Linux measurement in a disposable process, never enrolls an identity."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def rss_kib() -> int:
    if os.name == "nt":

        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak",
                    "working",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise RuntimeError("Process RSS measurement unavailable")
        return int(counters.working) // 1024
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    raise RuntimeError("Linux RSS measurement unavailable")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["hash", "api-disabled", "api-native"], default="hash")
    args = parser.parse_args()
    if args.mode.startswith("api-"):
        from apps.api.main import create_app
        from packages.core.config import Settings
        from packages.database.session import create_database_engine

        mode = args.mode.split("-", 1)[1]
        engine = create_database_engine("sqlite:///:memory:")
        app = create_app(Settings(environment="test", auth_mode=mode), engine)
        print(json.dumps({"mode": mode, "idle_rss_kib": rss_kib(), "routes": len(app.routes)}))
        engine.dispose()
        return

    from packages.auth.native import HASH_CONCURRENCY, HASHER, hash_slot, password_matches
    from packages.database.session import create_database_engine

    engine = create_database_engine("sqlite:///:memory:")
    encoded = HASHER.hash("disposable-benchmark-password")
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        with hash_slot(engine):
            assert password_matches(encoded, "disposable-benchmark-password")
        samples.append((time.perf_counter() - start) * 1000)
    idle = rss_kib()
    peaks = [idle]
    stop = threading.Event()

    def sample() -> None:
        while not stop.wait(0.005):
            peaks.append(rss_kib())

    def verify() -> None:
        with hash_slot(engine):
            assert password_matches(encoded, "disposable-benchmark-password")

    observer = threading.Thread(target=sample)
    observer.start()
    try:
        began = time.perf_counter()
        with ThreadPoolExecutor(max_workers=HASH_CONCURRENCY) as pool:
            list(pool.map(lambda _: verify(), range(HASH_CONCURRENCY)))
        concurrent_ms = (time.perf_counter() - began) * 1000
    finally:
        stop.set()
        observer.join()
        engine.dispose()
    print(
        json.dumps(
            {
                "argon2id_memory_kib": 65536,
                "iterations": 3,
                "parallelism": 1,
                "concurrency_limit": HASH_CONCURRENCY,
                "samples": len(samples),
                "verification_median_ms": round(statistics.median(samples), 2),
                "verification_max_ms": round(max(samples), 2),
                "two_concurrent_ms": round(concurrent_ms, 2),
                "idle_rss_kib": idle,
                "two_concurrent_peak_rss_kib": max(peaks),
                "rss_delta_kib": max(peaks) - idle,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
