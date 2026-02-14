import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "python"))
sys.path.insert(0, str(ROOT / "logics" / "python"))

from lxcharset import module  # noqa: E402


class TestPipeline(unittest.TestCase):
    def test_detect_with_pipeline(self) -> None:
        result = module.detect_with_pipeline("zażółć gęślą jaźń".encode("utf-8"))
        self.assertEqual(result.encoding, "utf-8")
        self.assertGreaterEqual(result.confidence, 0.70)


if __name__ == "__main__":
    unittest.main()
