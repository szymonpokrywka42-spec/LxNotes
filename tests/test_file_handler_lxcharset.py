import unittest
from dataclasses import dataclass
from unittest.mock import mock_open, patch

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


class _RaisingModule:
    def detect_encoding(self, raw_data):
        _ = raw_data
        raise RuntimeError("synthetic detect error")


class _NoHooksFeedback:
    """Feedback object without subscribe/unsubscribe API."""

    pass


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

    def test_detection_exception_falls_back_without_crash(self):
        logs = []

        def emit(msg, level):
            logs.append((msg, level))

        with patch.object(fh, "LXCHARSET_AVAILABLE", True), patch.object(
            fh, "lxcharset_module", _RaisingModule()
        ), patch.object(fh, "lxcharset_feedback", _FakeFeedback()):
            preferred, confidence = fh._detect_preferred_encoding(b"abc", "x.txt", emit)

        self.assertEqual(preferred, "")
        self.assertEqual(confidence, 0.0)
        self.assertTrue(any("LxCharset detection failed" in m for m, _ in logs))

    def test_detection_works_when_feedback_has_no_hooks(self):
        logs = []
        fake_module = _FakeModule(_Detection("utf-8", 0.97), feedback=None)

        def emit(msg, level):
            logs.append((msg, level))

        with patch.object(fh, "LXCHARSET_AVAILABLE", True), patch.object(
            fh, "lxcharset_module", fake_module
        ), patch.object(fh, "lxcharset_feedback", _NoHooksFeedback()):
            preferred, confidence = fh._detect_preferred_encoding(b"abc", "x.txt", emit)

        self.assertEqual(preferred, "utf-8")
        self.assertAlmostEqual(confidence, 0.97)
        self.assertTrue(any("detected encoding" in m.lower() for m, _ in logs))

    def test_open_worker_fallback_prefers_iso_8859_2_before_latin_1(self):
        worker = fh.OpenFileWorker(path="sample.txt")
        decoded = []
        fallback_order = []
        worker.finished.connect(decoded.append)

        def _fake_engine(raw_data, preferred_encoding, fallback_encodings):
            _ = raw_data, preferred_encoding
            fallback_order.append(list(fallback_encodings))
            return None

        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", mock_open(read_data=b"z\xb3oty")
        ), patch.object(fh, "_detect_preferred_encoding", return_value=("", 0.0)), patch.object(
            worker, "_decode_with_engine", side_effect=_fake_engine
        ):
            worker._run_open_task()

        self.assertTrue(fallback_order)
        self.assertLess(
            fallback_order[0].index("iso-8859-2"),
            fallback_order[0].index("latin-1"),
        )
        self.assertEqual(decoded, ["złoty"])
        self.assertIn(worker.used_encoding, {"cp1250", "iso-8859-2"})
        self.assertNotEqual(worker.used_encoding, "latin-1")


if __name__ == "__main__":
    unittest.main()
