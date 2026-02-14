from __future__ import annotations

from . import detector
from .detector import DetectionResult
from .feedback import FeedbackBus

try:
    from lxcharset_logics.pipeline import detect_with_pipeline as _detect_with_pipeline
except Exception:  # pragma: no cover - optional logic layer
    _detect_with_pipeline = None


class LxCharsetModule:
    def __init__(self, feedback_bus: FeedbackBus) -> None:
        self._feedback = feedback_bus
        detector.set_feedback_hook(self._feedback.emit)

    def detect_encoding(self, data: bytes) -> DetectionResult:
        self._feedback.debug("detect:start", "Starting detect_encoding", size=len(data))
        result = detector.detect_encoding(data)
        self._feedback.info(
            "detect:result",
            "Detection finished",
            encoding=result.encoding,
            confidence=round(result.confidence, 6),
            used_fallback=result.used_fallback,
            detected_by_bom=result.detected_by_bom,
        )
        return result

    def detect_with_pipeline(self, data: bytes) -> DetectionResult:
        if _detect_with_pipeline is None:
            self._feedback.warning(
                "pipeline:missing",
                "Pipeline package is not available, using detect_encoding",
                size=len(data),
            )
            return self.detect_encoding(data)

        self._feedback.debug("pipeline:start", "Starting detect_with_pipeline", size=len(data))
        result = _detect_with_pipeline(data)
        self._feedback.info(
            "pipeline:result",
            "Pipeline detection finished",
            encoding=result.encoding,
            confidence=round(result.confidence, 6),
            used_fallback=result.used_fallback,
            detected_by_bom=result.detected_by_bom,
        )
        return result

    @staticmethod
    def build_byte_frequency_table(data: bytes) -> list[int]:
        detector.emit_feedback("DEBUG", "module:byte-frequency-table", "Building byte frequency table", size=len(data))
        return detector.build_byte_frequency_table(data)

    @staticmethod
    def byte_frequency_ratio(data: bytes, byte_value: int) -> float:
        detector.emit_feedback(
            "DEBUG",
            "module:byte-frequency-ratio",
            "Calculating byte frequency ratio",
            size=len(data),
            byte_value=byte_value,
        )
        return detector.byte_frequency_ratio(data, byte_value)

    @staticmethod
    def build_ngram_frequency_table(text: str, n: int) -> dict[str, int]:
        detector.emit_feedback(
            "DEBUG",
            "module:ngram-table",
            "Building ngram frequency table",
            text_length=len(text),
            n=n,
        )
        return detector.build_ngram_frequency_table(text, n)

    @staticmethod
    def ngram_frequency_ratio(text: str, token: str) -> float:
        detector.emit_feedback(
            "DEBUG",
            "module:ngram-ratio",
            "Calculating ngram frequency ratio",
            text_length=len(text),
            token=token,
        )
        return detector.ngram_frequency_ratio(text, token)

    @staticmethod
    def analyze_polish_ngrams(text: str) -> float:
        detector.emit_feedback(
            "DEBUG",
            "module:polish-ngrams",
            "Analyzing polish ngrams",
            text_length=len(text),
        )
        return detector.analyze_polish_ngrams(text)
