# LxCharset Integration Contract (LxNotes)

This document defines the expected public API used by `LxNotes` from the local `LxCharset` module.

## Import Path Contract

`LxNotes` expects `LxCharset` Python sources to be available under:

- `LxCharset/Module/LxCharset/core/python`
- `LxCharset/Module/LxCharset/logics/python`

`core/file/file_handler.py` injects these paths into `sys.path` at runtime.

## Runtime API Contract

`file_handler.py` imports:

```python
from lxcharset import module as lxcharset_module, feedback as lxcharset_feedback
```

Required objects:

- `lxcharset_module.detect_encoding(data: bytes) -> DetectionResult-like`
- `lxcharset_feedback.subscribe(callback)`
- `lxcharset_feedback.unsubscribe(callback)`

## DetectionResult Contract

`LxNotes` reads these attributes from returned object:

- `encoding: str`
- `confidence: float`

Any custom object is acceptable as long as these attributes exist.

## Feedback Event Contract

Subscriber callback receives an `event` object with:

- `level` (`DEBUG|INFO|WARNING|ERROR|CRITICAL`)
- `code` (short event id)
- `message` (human-readable text)
- `context` (`dict` with extra fields, optional)

Events are forwarded to LxNotes console/log stream in form:

`[LxCharset] <code>: <message> | <k=v,...>`

## Compatibility Rule

As long as the above contract is preserved, `LxCharset` can be updated without modifying `LxNotes` `FileHandler`.
