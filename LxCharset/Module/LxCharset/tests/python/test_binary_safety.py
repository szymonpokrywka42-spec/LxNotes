import random
import unittest
from pathlib import Path
import sys
import importlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "python"))
sys.path.insert(0, str(ROOT / "logics" / "python"))

module = importlib.import_module("lxcharset").module  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
