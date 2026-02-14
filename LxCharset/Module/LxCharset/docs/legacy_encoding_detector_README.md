# Module: encoding_detector

Sandbox module for developing a custom encoding detector independent from Python `chardet`.

## Layout
- `cpp/include` - C++ public headers
- `cpp/src` - C++ implementation
- `python/lx_encoding` - Python wrapper / package API
- `tests/cpp` - native tests
- `tests/python` - Python integration tests
- `docs` - technical notes and design
- `scripts` - local helper scripts

## Workflow
1. Implement detection logic in C++.
2. Expose API to Python wrapper.
3. Validate with mixed-encoding fixtures and regression tests.
4. Integrate into main app only after sandbox acceptance.
