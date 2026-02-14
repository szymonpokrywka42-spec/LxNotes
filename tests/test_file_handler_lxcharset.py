import unittest
from dataclasses import dataclass
from unittest.mock import patch

from core.file import file_handler as fh


@dataclass
class _Detection:
    encoding: str
    confidence: float


class _FakeFeedback:
    def __init__(self, event=None):
        self._cb = None
        self._event = event

    def subscribe(self, cb):
        self._cb = cb

    def unsubscribe(self, cb):
        if self._cb is cb:
            self._cb = None

    def push_event(self):
        if self._cb and self._event is not None:
            self._cb(self._event)


class _FakeEvent:
    def __init__(self, level="INFO", code="x", message="m", context=None):
        self.level = level
        self.code = code
        self.message = message
        self.context = context or {}


class _FakeModule:
    def __init__(self, detection, feedback=None):
        self._detection = detection
        self._feedback = feedback

    def detect_encoding(self, raw_data):
        _ = raw_data
        if self._feedback:
            self._feedback.push_event()
        return self._detection


class TestLxCharsetBridge(unittest.TestCase):
    def test_unavailable_module_falls_back(self):
        logs = []

        def emit(msg, level):
            logs.append((msg, level))

        with patch.object(fh, "LXCHARSET_AVAILABLE", False):
            preferred, confidence = fh._detect_preferred_encoding(b"abc", "x.txt", emit)

        self.assertEqual(preferred, "")
        self.assertEqual(confidence, 0.0)
        self.assertTrue(any("LxCharset unavailable" in m for m, _ in logs))

    def test_low_confidence_ignores_preferred(self):
        logs = []
        fake_feedback = _FakeFeedback()
        fake_module = _FakeModule(_Detection("utf-8", 0.42), fake_feedback)

        def emit(msg, level):
            logs.append((msg, level))

        with patch.object(fh, "LXCHARSET_AVAILABLE", True), patch.object(
            fh, "lxcharset_module", fake_module
        ), patch.object(fh, "lxcharset_feedback", fake_feedback):
            preferred, confidence = fh._detect_preferred_encoding(b"abc", "x.txt", emit)

        self.assertEqual(preferred, "")
        self.assertAlmostEqual(confidence, 0.42)
        self.assertTrue(any("Low encoding confidence" in m for m, _ in logs))

    def test_feedback_event_is_forwarded_to_console(self):
        logs = []
        event = _FakeEvent(
            level="WARNING",
            code="detect:test",
            message="Synthetic feedback",
            context={"size": 3},
        )
        fake_feedback = _FakeFeedback(event=event)
        fake_module = _FakeModule(_Detection("utf-8", 0.97), fake_feedback)

        def emit(msg, level):
            logs.append((msg, level))

        with patch.object(fh, "LXCHARSET_AVAILABLE", True), patch.object(
            fh, "lxcharset_module", fake_module
        ), patch.object(fh, "lxcharset_feedback", fake_feedback):
            preferred, _ = fh._detect_preferred_encoding(b"abc", "x.txt", emit)

        self.assertEqual(preferred, "utf-8")
        self.assertTrue(
            any(
                level == "WARN" and "[LxCharset] detect:test: Synthetic feedback" in msg
                for msg, level in logs
            )
        )


if __name__ == "__main__":
    unittest.main()
