import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "python"))
sys.path.insert(0, str(ROOT / "logics" / "python"))

from lxcharset import feedback, module  # noqa: E402


class TestLxNotesContract(unittest.TestCase):
    def setUp(self) -> None:
        feedback.enable_console(False)
        feedback.disable_file_sink()

    def test_public_import_contract(self) -> None:
        self.assertTrue(hasattr(module, "detect_encoding"))
        self.assertTrue(callable(module.detect_encoding))
        self.assertTrue(hasattr(feedback, "subscribe"))
        self.assertTrue(callable(feedback.subscribe))
        self.assertTrue(hasattr(feedback, "unsubscribe"))
        self.assertTrue(callable(feedback.unsubscribe))

    def test_detect_result_shape_contract(self) -> None:
        result = module.detect_encoding(b"hello")
        self.assertTrue(hasattr(result, "encoding"))
        self.assertTrue(hasattr(result, "confidence"))
        self.assertIsInstance(result.encoding, str)
        self.assertIsInstance(result.confidence, float)

    def test_feedback_event_shape_contract(self) -> None:
        captured = []

        def on_event(event):
            captured.append(event)

        feedback.subscribe(on_event)
        try:
            module.detect_encoding(b"\xEF\xBB\xBFabc")
        finally:
            feedback.unsubscribe(on_event)

        self.assertGreater(len(captured), 0)
        event = captured[-1]
        self.assertTrue(hasattr(event, "level"))
        self.assertTrue(hasattr(event, "code"))
        self.assertTrue(hasattr(event, "message"))
        self.assertTrue(hasattr(event, "context"))


if __name__ == "__main__":
    unittest.main()
