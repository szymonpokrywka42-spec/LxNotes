#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path


def _load_fixtures(fixtures_dir: Path) -> list[bytes]:
    fixtures: list[bytes] = []
    if not fixtures_dir.exists():
        return fixtures
    for path in sorted(fixtures_dir.glob("*.txt")):
        try:
            fixtures.append(path.read_bytes())
        except OSError:
            continue
    return [f for f in fixtures if f]


def _mutate_payload(base: bytes, rng: random.Random) -> bytes:
    payload = bytearray(base)
    if not payload:
        payload = bytearray(os.urandom(rng.randint(1, 128)))

    mutation_count = rng.randint(1, 5)
    for _ in range(mutation_count):
        op = rng.choice(("flip", "insert", "delete", "slice", "append_noise"))

        if op == "flip" and payload:
            idx = rng.randrange(len(payload))
            payload[idx] ^= rng.randint(1, 255)
        elif op == "insert":
            idx = rng.randrange(len(payload) + 1)
            payload[idx:idx] = os.urandom(rng.randint(1, 16))
        elif op == "delete" and len(payload) > 4:
            start = rng.randrange(len(payload) - 1)
            end = min(len(payload), start + rng.randint(1, 24))
            del payload[start:end]
        elif op == "slice" and len(payload) > 8:
            start = rng.randrange(0, len(payload) // 2)
            end = rng.randrange(max(start + 1, len(payload) // 2), len(payload) + 1)
            payload = payload[start:end]
        elif op == "append_noise":
            payload.extend(os.urandom(rng.randint(1, 32)))

    # Keep fuzz runtime bounded but still meaningful.
    if len(payload) > 2_500_000:
        payload = payload[:2_500_000]
    return bytes(payload)


def _random_payload(rng: random.Random) -> bytes:
    mode = rng.choice(("small", "medium", "large", "structured"))
    if mode == "small":
        return os.urandom(rng.randint(0, 512))
    if mode == "medium":
        return os.urandom(rng.randint(513, 64_000))
    if mode == "large":
        return os.urandom(rng.randint(64_001, 350_000))

    chunk = rng.choice(
        [
            b"\x00\x00\x00\x00ABCD",
            b"\xEF\xBB\xBFhello",
            b"\xFF\xFEH\x00i\x00",
            "Zażółć gęślą jaźń\n".encode("utf-8"),
            "日本語テキスト\n".encode("utf-8"),
        ]
    )
    return chunk * rng.randint(1, 2000)


def run(cases: int, seed: int) -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "core" / "python"))
    sys.path.insert(0, str(root / "logics" / "python"))

    from lxcharset import feedback, module

    rng = random.Random(seed)
    fixtures = _load_fixtures(root / "tests" / "python" / "fixtures")
    feedback.enable_console(False)
    feedback.disable_file_sink()

    stats = Counter()
    timings_ms: list[float] = []
    encoding_hits: Counter[str] = Counter()
    failsafe_reasons: Counter[str] = Counter()

    def _on_event(event) -> None:
        if event.code == "detect:failsafe":
            reason = str(event.context.get("reason", "unknown"))
            failsafe_reasons[reason] += 1

    feedback.subscribe(_on_event)
    started = time.perf_counter()

    try:
        for i in range(cases):
            if fixtures and rng.random() < 0.50:
                base = rng.choice(fixtures)
                payload = _mutate_payload(base, rng)
                stats["mutated_cases"] += 1
            else:
                payload = _random_payload(rng)
                stats["random_cases"] += 1

            t0 = time.perf_counter()
            try:
                result = module.detect_encoding(payload)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                timings_ms.append(elapsed_ms)
                encoding_hits[result.encoding] += 1
                if result.used_fallback:
                    stats["fallback_cases"] += 1
            except Exception:
                stats["crashes"] += 1

            if (i + 1) % 1000 == 0:
                print(f"[fuzz] progress {i + 1}/{cases}")
    finally:
        feedback.unsubscribe(_on_event)

    total_s = time.perf_counter() - started
    done = max(1, cases)
    avg_ms = sum(timings_ms) / max(1, len(timings_ms))
    p95_ms = 0.0
    if timings_ms:
        ordered = sorted(timings_ms)
        p95_ms = ordered[int(0.95 * (len(ordered) - 1))]

    print("== LxCharset Fuzz Stability Report ==")
    print(f"cases={cases} seed={seed}")
    print(f"duration_s={total_s:.3f}")
    print(f"throughput_cases_per_s={cases / max(total_s, 1e-9):.2f}")
    print(f"crashes={stats['crashes']}")
    print(f"fallback_rate={(stats['fallback_cases'] / done) * 100:.2f}%")
    print(f"avg_latency_ms={avg_ms:.3f}")
    print(f"p95_latency_ms={p95_ms:.3f}")
    print(f"mutated_cases={stats['mutated_cases']}")
    print(f"random_cases={stats['random_cases']}")
    print("top_encodings=" + ", ".join(f"{enc}:{cnt}" for enc, cnt in encoding_hits.most_common(8)))
    if failsafe_reasons:
        print("failsafe_reasons=" + ", ".join(f"{k}:{v}" for k, v in failsafe_reasons.items()))
    else:
        print("failsafe_reasons=none")

    return 0 if stats["crashes"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Fuzz stability runner for LxCharset.")
    parser.add_argument("--cases", type=int, default=10000, help="Number of fuzz cases.")
    parser.add_argument("--seed", type=int, default=1337, help="PRNG seed for repeatability.")
    args = parser.parse_args()
    return run(cases=args.cases, seed=args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
