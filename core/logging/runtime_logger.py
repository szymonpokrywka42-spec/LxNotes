import atexit
import datetime
import faulthandler
import logging
import os
import sys
import threading
import traceback

_RUNTIME_READY = False
_RUNTIME_LOG_FILE = None
_CRASH_LOG_FILE = None
_LOCK = threading.Lock()


def _level_name_to_logging(level):
    mapping = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "SYSTEM": logging.INFO,
        "SUCCESS": logging.INFO,
        "BOOT": logging.INFO,
        "ACTION": logging.INFO,
        "FILE": logging.INFO,
        "ENGINE": logging.INFO,
        "EDITOR": logging.INFO,
        "UI": logging.INFO,
    }
    return mapping.get(str(level).upper(), logging.INFO)


def setup_runtime_logging(base_dir):
    global _RUNTIME_READY, _RUNTIME_LOG_FILE, _CRASH_LOG_FILE
    if _RUNTIME_READY:
        return

    logs_dir = os.path.join(base_dir, "assets", "logs")
    os.makedirs(logs_dir, exist_ok=True)

    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    runtime_path = os.path.join(logs_dir, f"runtime_{stamp}.log")
    crash_path = os.path.join(logs_dir, f"crash_{stamp}.log")

    _RUNTIME_LOG_FILE = open(runtime_path, "a", encoding="utf-8", buffering=1)
    _CRASH_LOG_FILE = open(crash_path, "a", encoding="utf-8", buffering=1)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stderr), logging.StreamHandler(_RUNTIME_LOG_FILE)],
        force=True,
    )

    faulthandler.enable(_CRASH_LOG_FILE, all_threads=True)

    def _unhandled_exception(exc_type, exc, tb):
        log = logging.getLogger("runtime")
        log.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        flush_runtime_logs()
        sys.__excepthook__(exc_type, exc, tb)

    def _thread_exception(args):
        log = logging.getLogger(f"thread.{args.thread.name}")
        log.critical("Unhandled thread exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        flush_runtime_logs()

    sys.excepthook = _unhandled_exception
    threading.excepthook = _thread_exception

    atexit.register(flush_runtime_logs)
    _RUNTIME_READY = True
    logging.getLogger("runtime").info("Runtime logging initialized.")


def get_logger(name):
    return logging.getLogger(name)


def log_message(level, message, source="app"):
    log = logging.getLogger(source)
    log.log(_level_name_to_logging(level), message)


def flush_runtime_logs():
    with _LOCK:
        root = logging.getLogger()
        for handler in root.handlers:
            try:
                handler.flush()
            except Exception:
                pass

        for fp in (_RUNTIME_LOG_FILE, _CRASH_LOG_FILE):
            if not fp:
                continue
            try:
                fp.flush()
                os.fsync(fp.fileno())
            except Exception:
                pass

