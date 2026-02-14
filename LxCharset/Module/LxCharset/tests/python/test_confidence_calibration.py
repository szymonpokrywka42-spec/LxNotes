import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "python"))
sys.path.insert(0, str(ROOT / "logics" / "python"))

from lxcharset.detector import probe_single_byte_encoding  # noqa: E402


class TestConfidenceCalibration(unittest.TestCase):
    def test_ambiguous_single_byte_confidence_is_capped(self) -> None:
        # Bytes chosen to be plausible in both cp1250 and iso-8859-2 paths.
        payload = bytes([0xA1, 0xA5, 0xB1, 0xB9, 0xC6, 0xE6, 0xCA, 0xEA] * 200)
        result = probe_single_byte_encoding(payload)
        self.assertIsNotNone(result)
        _, confidence = result
        self.assertLessEqual(confidence, 0.72)


if __name__ == "__main__":
    unittest.main()
