"""LxCharset core API."""

from .detector import (
    DetectionResult,
    analyze_polish_ngrams,
    build_byte_frequency_table,
    build_ngram_frequency_table,
    byte_frequency_ratio,
    detect_encoding,
    emit_feedback,
    ngram_frequency_ratio,
    set_feedback_hook,
)
from .feedback import FeedbackBus, FeedbackEvent
from .module_api import LxCharsetModule

feedback = FeedbackBus()
module = LxCharsetModule(feedback)

__all__ = [
    "DetectionResult",
    "FeedbackEvent",
    "FeedbackBus",
    "LxCharsetModule",
    "module",
    "feedback",
    "detect_encoding",
    "set_feedback_hook",
    "emit_feedback",
    "build_byte_frequency_table",
    "byte_frequency_ratio",
    "build_ngram_frequency_table",
    "ngram_frequency_ratio",
    "analyze_polish_ngrams",
]
