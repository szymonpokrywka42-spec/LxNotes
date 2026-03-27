from __future__ import annotations

import sys
import threading
import traceback
from datetime import date
from pathlib import Path

from .feedback import feedback

_INSTALLED = False
_LOG_PATH: Path | None = None


class FatalRuntimeError(RuntimeError):
    pass


def _default_log_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent] + list(here.parent.parents):
        if (parent / "assets").exists():
            return parent / "assets" / "logs"
        if (parent / "pyproject.toml").exists():
            return parent / "assets" / "logs"
    return here.parent / ".binman" / "logs"


def install_error_trap(log_dir: str | Path | None = None) -> Path:
    """
    Install global handlers that log any uncaught exception.
    Process termination is left to Python's default uncaught-exception
    semantics; this helper avoids hard-killing host processes.
    """
    global _INSTALLED, _LOG_PATH
    if _INSTALLED:
        return _LOG_PATH or _default_log_dir()

    log_directory = Path(log_dir) if log_dir else _default_log_dir()
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / f"lxbinman_{date.today()}.log"
    feedback.set_file_sink(str(log_path))

    def _fatal(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        feedback.emit("ERROR", "UNCAUGHT", text)

    def _thread_hook(args):
        _fatal(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = _fatal
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_hook  # type: ignore[assignment]

    _INSTALLED = True
    _LOG_PATH = log_path
    return log_path


def fatal(code: str, message: str | None = None, exc: BaseException | None = None) -> None:
    """Log and raise a fatal runtime exception."""
    if exc:
        msg = message or f"{exc}"
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        feedback.emit("ERROR", code, f"{msg}\n{tb}")
        raise FatalRuntimeError(msg) from exc
    else:
        msg = message or "fatal error"
        feedback.emit("ERROR", code, msg)
        raise FatalRuntimeError(msg)
