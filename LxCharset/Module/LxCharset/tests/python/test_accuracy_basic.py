import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "python"))
sys.path.insert(0, str(ROOT / "logics" / "python"))

from lxcharset import module  # noqa: E402


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class TestAccuracyBasic(unittest.TestCase):
    def _detect(self, fixture_name: str):
        data = (FIXTURES_DIR / fixture_name).read_bytes()
        return module.detect_encoding(data)

    def test_utf8_fixture(self):
        result = self._detect("utf8.txt")
        self.assertEqual(result.encoding, "utf-8")
        self.assertGreaterEqual(result.confidence, 0.70)

    def test_utf16le_fixture(self):
        result = self._detect("utf16le.txt")
        self.assertEqual(result.encoding, "utf-16-le")
        self.assertGreaterEqual(result.confidence, 0.90)

    def test_utf16be_fixture(self):
        result = self._detect("utf16be.txt")
        self.assertEqual(result.encoding, "utf-16-be")
        self.assertGreaterEqual(result.confidence, 0.90)

    def test_cp1250_fixture(self):
        result = self._detect("cp1250.txt")
        self.assertEqual(result.encoding, "windows-1250")
        self.assertGreaterEqual(result.confidence, 0.55)

    def test_iso88592_fixture(self):
        result = self._detect("iso88592.txt")
        self.assertEqual(result.encoding, "iso-8859-2")
        self.assertGreaterEqual(result.confidence, 0.55)

    def test_latin1_fixture(self):
        result = self._detect("latin1.txt")
        # Latin-1 sample is expected to be routed through single-byte branch.
        self.assertIn(result.encoding, {"windows-1250", "iso-8859-2", "latin-1"})
        self.assertGreaterEqual(result.confidence, 0.30)


if __name__ == "__main__":
    unittest.main()
