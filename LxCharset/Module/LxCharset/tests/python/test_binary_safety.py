import random
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "python"))
sys.path.insert(0, str(ROOT / "logics" / "python"))

from lxcharset import module  # noqa: E402
from lxcharset import feedback  # noqa: E402


class TestBinarySafety(unittest.TestCase):
    def test_random_binary_fallback(self) -> None:
        rng = random.Random(1337)
        data = bytes(rng.getrandbits(8) for _ in range(200_000))
        result = module.detect_encoding(data)
        self.assertTrue(result.used_fallback)
        self.assertLessEqual(result.confidence, 0.2)

    def test_nul_heavy_binary_fallback(self) -> None:
        data = (b"\x00\x01\x02\x03" * 20_000) + b"binary-tail"
        result = module.detect_encoding(data)
        self.assertTrue(result.used_fallback)
        self.assertLessEqual(result.confidence, 0.2)

    def test_magic_header_binary_fallback(self) -> None:
        # PNG signature should trigger hard binary classification quickly.
        data = b"\x89PNG\r\n\x1a\n" + (b"\x00\x10\x20\x30" * 4000)
        result = module.detect_encoding(data)
        self.assertTrue(result.used_fallback)
        self.assertLessEqual(result.confidence, 0.2)

    def test_utf16le_ascii_pattern_not_flagged_as_binary_guard(self) -> None:
        # UTF-16 LE without BOM should not be misclassified by binary guard due NUL bytes.
        events: list[str] = []

        def _cb(event) -> None:
            events.append(event.code)

        feedback.subscribe(_cb)
        try:
            data = "Hello from LxCharset".encode("utf-16-le")
            _ = module.detect_encoding(data)
        finally:
            feedback.unsubscribe(_cb)

        self.assertNotIn("core:binary-guard", events)
        self.assertNotIn("core:utf8-binary-guard", events)


if __name__ == "__main__":
    unittest.main()
