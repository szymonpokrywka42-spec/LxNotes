# LxCharset Roadmap (Execution Order)

This roadmap is aligned with current LxNotes integration and stress-test findings.
Priority is: keep `LxNotes` contract stable and improve correctness/performance internally.

## Phase 0: Guardrails (Done)

1. Keep stable public API for LxNotes:
- `from lxcharset import module, feedback`
- `module.detect_encoding(data: bytes)` returning `encoding` + `confidence`
- `feedback.subscribe/unsubscribe` and event shape
2. Add contract tests (`test_lxnotes_contract.py`)

## Phase 1: Accuracy Baseline (Done)

1. Add fixtures and tests for:
- `utf-8`, `utf-16-le`, `utf-16-be`
- `windows-1250`, `iso-8859-2`, `latin-1` path
- `shift_jis`, `euc_jp`, `big5`
2. Keep all tests green in `run_py_tests.sh`

## Phase 2: Binary Safety (Next)

Problem found in stress tests:
- random binary data is often classified as text single-byte (`iso-8859-2`) with high confidence.

Tasks:
1. Add binary guard heuristic before single-byte/multi-byte scoring:
- NUL ratio
- control-byte ratio
- estimated entropy / printable-ratio
2. Return low-confidence fallback for binary-looking payloads.
3. Add regression tests:
- random payload should not produce high-confidence text classification.

Definition of done:
- random 1MB/10MB payloads no longer return high-confidence legacy text guesses.

## Phase 3: Performance Hardening

Tasks:
1. Optimize slow path on large binary input.
2. Add optional sampling mode for heavy payloads in detection stage.
3. Keep early-exit path efficient for valid UTF-heavy text.

Definition of done:
- improve random binary throughput vs baseline stress run.
- preserve current UTF throughput and accuracy.

## Phase 4: Confidence Calibration

Tasks:
1. Rebalance confidence function for ambiguous single-byte cases.
2. Add confidence cap when ambiguity or binary suspicion is high.
3. Add calibration fixtures where wrong high-confidence guesses were observed.

Definition of done:
- fewer false positives with confidence > 0.8 on ambiguous input.

## Phase 5: Feedback/Observability

Tasks:
1. Add verbosity modes (e.g. `quiet`, `normal`, `debug`) to reduce log spam.
2. Keep event schema backward-compatible for LxNotes console bridge.
3. Add stress summary output (latency + outcome buckets).

Definition of done:
- logs remain readable in app console under heavy workloads.

## Phase 6: C++ Parity and Rollout

Tasks:
1. Mirror key binary-safety and confidence logic in C++ implementation.
2. Ensure Python/C++ behavior parity on fixture suite.
3. Freeze release notes and version bump for module update.

Definition of done:
- parity tests green + no LxNotes-side adapter changes needed.
