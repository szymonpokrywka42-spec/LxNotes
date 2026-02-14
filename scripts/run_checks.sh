#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[LxNotes] Checks: START"
python3 -m py_compile main.py
python3 -m py_compile core/file/file_handler.py
python3 -m py_compile core/editor/console_logic.py
python3 -m unittest -v tests/test_file_handler_lxcharset.py
echo "[LxNotes] Checks: OK"
