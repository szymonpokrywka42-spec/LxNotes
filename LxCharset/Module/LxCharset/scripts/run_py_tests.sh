#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/core/python:$ROOT/logics/python:${PYTHONPATH:-}"

echo "[LxCharset] Python checks: START"
echo "[LxCharset] Root: $ROOT"
python3 -m unittest discover -s "$ROOT/tests/python" -p "test_*.py" -v
echo "[LxCharset] Python checks: OK"
