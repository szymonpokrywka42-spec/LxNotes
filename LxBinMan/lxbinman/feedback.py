from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TextIO


@dataclass
class FeedbackEvent:
    timestamp: str
    level: str
    code: str
    message: str
    context: dict[str, Any]


class FeedbackBus:
    def __init__(self) -> None:
        self._subscribers: list[Callable[[FeedbackEvent], None]] = []
        self._history: list[FeedbackEvent] = []
        self._history_limit = 500
        self._console_enabled = True
        self._file_path: Path | None = None
        self._file_handle: TextIO | None = None
        self._kill_on_error = False
        self._init_default_sink()

    def _default_log_path(self) -> Path:
        here = Path(__file__).resolve()
        for parent in [here.parent] + list(here.parent.parents):
            if (parent / "assets").exists():
                return parent / "assets" / "logs" / "lxbinman.log"
            if (parent / "pyproject.toml").exists():
                return parent / "assets" / "logs" / "lxbinman.log"
        return here.parent / ".binman" / "logs" / "lxbinman.log"

    def _init_default_sink(self) -> None:
        try:
            self.set_file_sink(str(self._default_log_path()))
        except Exception:
            # Best-effort; console logging will still work.
            pass

    def subscribe(self, callback: Callable[[FeedbackEvent], None]) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[FeedbackEvent], None]) -> None:
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def enable_console(self, enabled: bool = True) -> None:
        self._console_enabled = bool(enabled)

    def set_kill_on_error(self, enabled: bool = True) -> None:
        self._kill_on_error = bool(enabled)

    def set_file_sink(self, file_path: str) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self._file_handle is not None:
            self._file_handle.close()
        self._file_path = path
        self._file_handle = path.open("a", encoding="utf-8", buffering=1)

    def disable_file_sink(self) -> None:
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None
        self._file_path = None

    def emit(self, level: str, code: str, message: str, **context: Any) -> FeedbackEvent:
        event = FeedbackEvent(
            timestamp=datetime.now().isoformat(timespec="milliseconds"),
            level=level.upper(),
            code=code,
            message=message,
            context=context,
        )
        self._history.append(event)
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit :]

        line = self.format_event(event)
        if self._console_enabled:
            print(line, flush=True)
        if self._file_handle is not None:
            self._file_handle.write(line + "\n")
        for callback in list(self._subscribers):
            callback(event)
        return event

    def debug(self, code: str, message: str, **context: Any) -> FeedbackEvent:
        return self.emit("DEBUG", code, message, **context)

    def info(self, code: str, message: str, **context: Any) -> FeedbackEvent:
        return self.emit("INFO", code, message, **context)

    def success(self, code: str, message: str, **context: Any) -> FeedbackEvent:
        return self.emit("SUCCESS", code, message, **context)

    def warning(self, code: str, message: str, **context: Any) -> FeedbackEvent:
        return self.emit("WARNING", code, message, **context)

    def error(self, code: str, message: str, **context: Any) -> FeedbackEvent:
        evt = self.emit("ERROR", code, message, **context)
        if self._kill_on_error:
            raise RuntimeError(f"{code}: {message}")
        return evt

    def history(self) -> list[FeedbackEvent]:
        return list(self._history)

    def close(self) -> None:
        self.disable_file_sink()

    def __del__(self) -> None:
        self.close()

    @staticmethod
    def format_event(event: FeedbackEvent) -> str:
        if event.context:
            ctx = ", ".join(f"{k}={v}" for k, v in event.context.items())
            return f"{event.timestamp} [{event.level}] {event.code}: {event.message} | {ctx}"
        return f"{event.timestamp} [{event.level}] {event.code}: {event.message}"


feedback = FeedbackBus()
