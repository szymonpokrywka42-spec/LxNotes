import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "python"))
sys.path.insert(0, str(ROOT / "logics" / "python"))

from lxcharset import feedback, module  # noqa: E402


class TestDetector(unittest.TestCase):
    def setUp(self) -> None:
        feedback.enable_console(False)
        feedback.disable_file_sink()

    def test_detect_utf8_bom(self) -> None:
        result = module.detect_encoding(b"\xEF\xBB\xBFhello")
        self.assertEqual(result.encoding, "utf-8-sig")
        self.assertGreaterEqual(result.confidence, 0.99)

    def test_early_exit_large_payload(self) -> None:
        payload = b"\xEF\xBB\xBF" + ("zażółć\n".encode("utf-8") * 2000)
        result = module.detect_encoding(payload)
        self.assertEqual(result.encoding, "utf-8-sig")
        self.assertGreaterEqual(result.confidence, 0.99)

    def test_feedback_file_sink_writes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "lxcharset.log"
            feedback.set_file_sink(str(log_path))
            module.detect_encoding(b"\xEF\xBB\xBFabc")
            self.assertTrue(log_path.exists())
            content = log_path.read_text(encoding="utf-8")
            self.assertIn("detect:result", content)


if __name__ == "__main__":
    unittest.main()
