#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(dirname "$0")"
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$ROOT_DIR/.build-tests"

echo "[LxCharset] C++ checks: START"
echo "[LxCharset] Root: $ROOT_DIR"
mkdir -p "$BUILD_DIR"

echo "[LxCharset] Configure core/cpp"
cmake -S "$ROOT_DIR/core/cpp" -B "$BUILD_DIR/core"

echo "[LxCharset] Build core/cpp"
cmake --build "$BUILD_DIR/core"

echo "[LxCharset] Configure logics/cpp"
cmake -S "$ROOT_DIR/logics/cpp" -B "$BUILD_DIR/logics"

echo "[LxCharset] Build logics/cpp"
cmake --build "$BUILD_DIR/logics"

echo "[LxCharset] C++ checks: OK"
