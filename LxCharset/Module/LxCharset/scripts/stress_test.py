#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def run(fuzz_cases: int, threaded_jobs: int, workers: int) -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "core" / "python"))
    sys.path.insert(0, str(root / "logics" / "python"))

    from lxcharset import feedback, module

    feedback.enable_console(False)
    feedback.disable_file_sink()

    print("== STRESS START ==")
    cases = [
        ("utf8_4k", ("Zażółć gęślą jaźń\n" * 200).encode("utf-8")),
        ("utf8_1mb", ("abcżółć日本語" * 60000).encode("utf-8")[:1_000_000]),
        ("utf8_10mb", ("abcżółć日本語" * 700000).encode("utf-8")[:10_000_000]),
        ("rand_1mb", os.urandom(1_000_000)),
        ("rand_10mb", os.urandom(10_000_000)),
    ]

    for name, data in cases:
        t0 = time.perf_counter()
        result = module.detect_encoding(data)
        dt = time.perf_counter() - t0
        mb = len(data) / 1_000_000
        thr = (mb / dt) if dt > 0 else 0.0
        print(
            f"[single] {name:9s} {mb:6.2f}MB {dt:7.4f}s {thr:7.2f}MB/s -> "
            f"{result.encoding} conf={result.confidence:.3f} fb={result.used_fallback}"
        )

    repeat_data = ("To jest test wydajności UTF-8. 日本語 big5?\n" * 2000).encode("utf-8")
    repeat_n = 1000
    t0 = time.perf_counter()
    for _ in range(repeat_n):
        module.detect_encoding(repeat_data)
    dt = time.perf_counter() - t0
    print(f"[repeat] {repeat_n} calls on {len(repeat_data)} bytes in {dt:.3f}s => {repeat_n/dt:.1f} calls/s")

    random.seed(1337)
    failures = 0
    t0 = time.perf_counter()
    for i in range(fuzz_cases):
        size = random.randint(0, 50000)
        payload = os.urandom(size)
        try:
            module.detect_encoding(payload)
        except Exception:
            failures += 1
        if (i + 1) % 200 == 0:
            print(f"[fuzz] progress {i + 1}/{fuzz_cases}")
    print(f"[fuzz] done {fuzz_cases} payloads in {time.perf_counter() - t0:.3f}s failures={failures}")

    pool_data = [
        ("Zażółć gęślą jaźń" * 120).encode("utf-8"),
        ("日本語テキストです。" * 120).encode("euc_jp", errors="ignore"),
        os.urandom(20000),
    ]

    def task(i: int) -> str:
        return module.detect_encoding(pool_data[i % 3]).encoding

    t0 = time.perf_counter()
    errors = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(task, i) for i in range(threaded_jobs)]
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception:
                errors += 1
    print(f"[thread] workers={workers} jobs={threaded_jobs} time={time.perf_counter() - t0:.3f}s errs={errors}")
    print("history_size", len(feedback.history()))
    print("== STRESS END ==")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress test for LxCharset Python detector.")
    parser.add_argument("--fuzz-cases", type=int, default=800)
    parser.add_argument("--threaded-jobs", type=int, default=600)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    return run(args.fuzz_cases, args.threaded_jobs, args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
