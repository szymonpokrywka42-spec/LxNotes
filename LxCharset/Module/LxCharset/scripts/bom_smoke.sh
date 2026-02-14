#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(dirname "$0")"
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="$ROOT_DIR"

cd "$ROOT_DIR"
python3 - << 'PY'
import sys
from core.python.lxcharset.detector import detect_encoding

samples = {
    'utf32be_bom': b'\x00\x00\xFE\xFF\x00\x00\x00A',
    'utf32le_bom': b'\xFF\xFE\x00\x00A\x00\x00\x00',
    'utf8_bom': b'\xEF\xBB\xBFhello',
    'utf16be_bom': b'\xFE\xFF\x00h\x00i',
    'utf16le_bom': b'\xFF\xFEh\x00i\x00',
    'plain': b'hello',
}

print('[LxCharset] BOM smoke: START')
print(f'[LxCharset] Python: {sys.executable}')
for name, data in samples.items():
    result = detect_encoding(data)
    print(f"{name}: {result.encoding} conf={result.confidence} fallback={result.used_fallback} bom={result.detected_by_bom}")
print('[LxCharset] BOM smoke: DONE')
PY
