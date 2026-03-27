# LxNotes Stability Notes

## Scope
This document captures stability-driven decisions introduced during the recent hardening and refactor work.

## File I/O Architecture
- `core/file/file_handler.py` is now an orchestrator layer.
- Open/save finalization logic is delegated to:
  - `core/file/operation_flows.py` -> `OpenFlow`
  - `core/file/operation_flows.py` -> `SaveFlow`
- Worker lifecycle state is centralized in `WorkerRegistry`:
  - active workers map
  - canceled workers set
  - cleanup + cancel marker management

## Worker Model
- Workers are split by responsibility:
  - `OpenFileWorker`
  - `SaveFileWorker`
- Compatibility factory is preserved:
  - `FileWorker(task_type, path, content=None)`
- Open pipeline keeps strict failover:
  - engine decode attempt
  - Python fallback codecs
  - UTF-8 replace mode as last resort

## Cancel Safety
- Cancel path uses `requestInterruption()` instead of hard terminate.
- Canceled workers are marked and ignored in late `finished/error` signal handlers.
- Cleanup strategy:
  - immediate removal from active map
  - cancel marker kept until late signal path is safely consumed

## Large Viewer Stability
- Large file mode remains read-only chunked viewing with explicit full-edit transition.
- Critical behaviors covered by tests:
  - activation + state/label correctness
  - chunk switching correctness
  - conversion to full editable content
  - keypress edit block + one-time read-only hint

## i18n Runtime Policy
- Runtime messages for console and file operations now use translation keys with default fallback text.
- Product terms are kept consistent across languages:
  - `GoToLine`
  - `Large Viewer`
  - `Turbo` / `Turbo Mode`
- Language consistency test enforces:
  - all locale files include base keys from `en-us.json`
  - required product tokens are present in designated runtime strings

## Test Baseline
- Current regression baseline includes:
  - file operation flow tests
  - cancel/late-signal safety tests
  - LxCharset bridge tests
  - console help tests
  - dialog smoke tests (offscreen)
  - language key consistency tests
  - large viewer tests

## Known Tradeoffs
- Font settings dialog runs in safe mode to avoid platform-specific PyQt crashes:
  - initialization does not depend on direct editor state reads
  - prioritizes stability over full contextual prefill behavior

## Next Recommended Work
- Add a focused integration test for `Save As` overwrite confirmation flow.
- Continue polishing natural language quality in remaining locales while preserving product term tokens.
