# Module: LxCharset

`LxCharset` is a headless encoding-detection module (no UI), designed to replace external `chardet` usage with a custom engine.

## Layout
- `core` - detector engine, feedback bus, public Python API
- `logics` - high-level pipeline wrappers
- `tests` - Python and C++ checks
- `docs` - roadmap and technical notes
- `scripts` - local test/build helpers

## Quick Start (Integration)

```python
from lxcharset import module, feedback

feedback.enable_console(True)
feedback.set_file_sink("logs/lxcharset.log")

result = module.detect_encoding(raw_bytes)
print(result.encoding, result.confidence)
```

## API Entry Points

- `module` - all main module capabilities:
- `module.detect_encoding(data: bytes)`
- `module.detect_with_pipeline(data: bytes)`
- `module.build_byte_frequency_table(data: bytes)`
- `module.byte_frequency_ratio(data: bytes, byte_value: int)`
- `module.build_ngram_frequency_table(text: str, n: int)`
- `module.ngram_frequency_ratio(text: str, token: str)`
- `module.analyze_polish_ngrams(text: str)`
- `feedback` - all module feedback/events:
- `feedback.enable_console(True|False)`
- `feedback.set_file_sink(path)`
- `feedback.disable_file_sink()`
- `feedback.subscribe(callback)`
- `feedback.history()`

## Performance Notes

- Fast integration path: single import `from lxcharset import module, feedback`
- Feedback path optimized for low latency:
- detector emits structured events through one hook
- file sink uses persistent line-buffered handle (no reopen per event)
- Early exit: when first 4KB reaches confidence `> 0.98`, full-pass is skipped

## Tests

```bash
./scripts/run_py_tests.sh
./scripts/run_cpp_tests.sh
./scripts/run_all_tests.sh
```

## Creator
- Szymon Pokrywka
