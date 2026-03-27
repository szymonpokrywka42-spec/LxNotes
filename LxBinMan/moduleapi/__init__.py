import warnings

from .autobin import AutoBinError, load, load_many, runtime_info
from lxbinman.feedback import FeedbackBus, FeedbackEvent, feedback

warnings.warn(
    "moduleapi is a compatibility layer and will be deprecated in a future release; "
    "prefer importing from `lxbinman` directly.",
    DeprecationWarning,
    stacklevel=2,
)

from . import builder

__all__ = [
    "AutoBinError",
    "load",
    "load_many",
    "runtime_info",
    "FeedbackBus",
    "FeedbackEvent",
    "feedback",
    "builder",
]
