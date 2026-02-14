# Contributing to LxNotes

Thanks for contributing. This document describes the expected workflow and architecture boundaries.

## Project Structure

- `main.py` - app entry point and setup/bootstrap flow.
- `ui/` - PyQt6 window, dialogs, menus, visual behavior.
- `core/` - editor/file/theme/logging logic.
- `core/cengines/` - native C++ `lx_engine` implementation.
- `LxCharset/` - bundled charset module used by `FileHandler`.

## Key Integration Rules

- Encoding detection in LxNotes is done through local `LxCharset`, not external `chardet`.
- `FileHandler` expects a stable API from `LxCharset`.
- Full contract is documented in `docs/LXCHARSET_API.md`.
- If you change `LxCharset` internals, keep this contract stable to avoid LxNotes-side edits.

## Local Development

1. Create a branch from current main/stable line.
2. Make focused changes (one concern per PR).
3. Run checks locally:

```bash
./scripts/run_checks.sh
```

4. Confirm app behavior manually:
- start app
- open/save files
- verify F12 console logs
- verify charset detection logs during file-open

## CI

- GitHub Actions workflow: `.github/workflows/lxnotes-ci.yml`
- CI runs `./scripts/run_checks.sh` on push/PR.
- Keep CI green before requesting review.

## Localization

Translations are in `assets/languages`.

Rules:
- copy an existing locale file, e.g. `en-us.json`
- rename to target locale code, e.g. `fr-fr.json`
- translate only values, keep keys unchanged

Language list shown in settings must include the new locale mapping in `ui/dialogs/settings_dialog.py`.

## PR Quality Expectations

- No unrelated refactors in the same PR.
- Keep logs meaningful; avoid noisy debug leftovers.
- Preserve backward compatibility for config/session behavior.
- Update `README.md` and/or `docs/` when behavior or contracts change.
