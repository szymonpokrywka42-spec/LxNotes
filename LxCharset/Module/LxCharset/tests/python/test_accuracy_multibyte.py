import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "python"))
sys.path.insert(0, str(ROOT / "logics" / "python"))

from lxcharset import module  # noqa: E402


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class TestAccuracyMultibyte(unittest.TestCase):
    def _detect(self, fixture_name: str):
        data = (FIXTURES_DIR / fixture_name).read_bytes()
        return module.detect_encoding(data)

    def test_shift_jis_fixture(self):
        result = self._detect("shift_jis.txt")
        self.assertEqual(result.encoding, "shift_jis")
        self.assertGreaterEqual(result.confidence, 0.55)

    def test_euc_jp_fixture(self):
        result = self._detect("euc_jp.txt")
        self.assertEqual(result.encoding, "euc_jp")
        self.assertGreaterEqual(result.confidence, 0.55)

    def test_big5_fixture(self):
        result = self._detect("big5.txt")
        self.assertEqual(result.encoding, "big5")
        self.assertGreaterEqual(result.confidence, 0.55)


if __name__ == "__main__":
    unittest.main()
