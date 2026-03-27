import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "python"))
sys.path.insert(0, str(ROOT / "logics" / "python"))

from lxcharset import feedback, module  # noqa: E402
from lxcharset import detector  # noqa: E402


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

    def test_detect_accepts_bytearray_input(self) -> None:
        result = module.detect_encoding(bytearray(b"hello world"))
        self.assertIsInstance(result.encoding, str)
        self.assertGreaterEqual(result.confidence, 0.0)

    def test_detect_failsafe_on_internal_exception(self) -> None:
        original = detector._detect_encoding_core

        def _raise(_: bytes):
            raise RuntimeError("boom")

        detector._detect_encoding_core = _raise
        try:
            result = module.detect_encoding(b"abc")
        finally:
            detector._detect_encoding_core = original

        self.assertEqual(result.encoding, "utf-8")
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.confidence, 0.0)

    def test_large_utf8_multibyte_payload_stays_utf8(self) -> None:
        # Regression: sampled large payload must not become synthetic invalid stream.
        payload = "€" * 700_000
        result = module.detect_encoding(payload.encode("utf-8"))
        self.assertEqual(result.encoding, "utf-8")
        self.assertGreaterEqual(result.confidence, 0.70)

    def test_detect_accepts_unsized_generator_without_exception(self) -> None:
        def _chunk_generator():
            yield b"hello"
            yield b"world"

        result = module.detect_encoding(_chunk_generator())

        self.assertEqual(result.encoding, "utf-8")
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
