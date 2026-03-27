import atexit
import datetime
import faulthandler
import logging
import os
import sys
import threading
import time
import traceback

_RUNTIME_READY = False
_RUNTIME_LOG_FILE = None
_CRASH_LOG_FILE = None
_LOCK = threading.Lock()
_PENDING_FSYNC = 0
_LAST_DURABLE_FLUSH = 0.0
_FLUSH_INTERVAL_SECONDS = 0.25
_FLUSH_EVERY_WRITES = 25


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
    global _RUNTIME_READY, _RUNTIME_LOG_FILE, _CRASH_LOG_FILE, _LAST_DURABLE_FLUSH, _PENDING_FSYNC
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
        _mark_runtime_activity()
        flush_runtime_logs(force=True)
        sys.__excepthook__(exc_type, exc, tb)

    def _thread_exception(args):
        log = logging.getLogger(f"thread.{args.thread.name}")
        log.critical("Unhandled thread exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        _mark_runtime_activity()
        flush_runtime_logs(force=True)

    sys.excepthook = _unhandled_exception
    threading.excepthook = _thread_exception

    atexit.register(flush_runtime_logs)
    _LAST_DURABLE_FLUSH = time.monotonic()
    _PENDING_FSYNC = 0
    _RUNTIME_READY = True
    logging.getLogger("runtime").info("Runtime logging initialized.")
    _mark_runtime_activity()


def get_logger(name):
    return logging.getLogger(name)


def log_message(level, message, source="app"):
    log = logging.getLogger(source)
    log.log(_level_name_to_logging(level), message)
    _mark_runtime_activity()
    flush_runtime_logs()


def _mark_runtime_activity():
    global _PENDING_FSYNC
    if not _RUNTIME_READY:
        return
    with _LOCK:
        _PENDING_FSYNC += 1


def flush_runtime_logs(force=False):
    global _PENDING_FSYNC, _LAST_DURABLE_FLUSH
    with _LOCK:
        if not _RUNTIME_READY:
            return

        now = time.monotonic()
        if not force:
            if _PENDING_FSYNC <= 0:
                return
            if _PENDING_FSYNC < _FLUSH_EVERY_WRITES and (now - _LAST_DURABLE_FLUSH) < _FLUSH_INTERVAL_SECONDS:
                return

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

        _PENDING_FSYNC = 0
        _LAST_DURABLE_FLUSH = now
