from __future__ import annotations

import warnings

from lxbinman.feedback import FeedbackBus, FeedbackEvent, feedback

warnings.warn(
    "moduleapi.feedback is a compatibility layer; prefer `lxbinman.feedback`.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["FeedbackBus", "FeedbackEvent", "feedback"]
