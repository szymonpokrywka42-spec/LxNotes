import warnings

from .autobin import AutoBinError, load, load_many, runtime_info
from .manifest import cache_key, is_manifest_compatible, read_manifest

warnings.warn(
    "binman is a compatibility layer and will be deprecated in a future release; "
    "prefer importing from `lxbinman` directly.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "AutoBinError",
    "load",
    "load_many",
    "runtime_info",
    "cache_key",
    "is_manifest_compatible",
    "read_manifest",
]
