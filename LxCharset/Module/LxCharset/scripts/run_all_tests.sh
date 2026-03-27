#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(dirname "$0")"
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[LxCharset] All checks: START"
"$ROOT_DIR/scripts/run_cpp_tests.sh"
"$ROOT_DIR/scripts/run_py_tests.sh"
echo "[LxCharset] All checks: DONE"
