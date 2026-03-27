import os
import json
import sys
import tempfile
import threading
from core.logging import log_message

class RecentFiles:
    def __init__(self, console_logic=None, max_items=10):
        # Przechowujemy referencję do logiki konsoli
        self.console = console_logic
        self.max_items = max_items
        self.recent_files = []
        self._lock = threading.RLock()
        self._last_saved_state = None
        self.config_path = self._get_config_path()
        self.legacy_config_path = os.path.join(os.path.expanduser("~"), ".lxnotes_recent.json")
        self.load()

    def _get_config_path(self):
        home_dir = os.path.expanduser("~")
        if os.name == "nt":
            base_config_dir = os.getenv("APPDATA", home_dir)
        elif sys.platform == "darwin":
            base_config_dir = os.path.join(home_dir, "Library", "Application Support")
        else:
            base_config_dir = os.getenv("XDG_CONFIG_HOME", os.path.join(home_dir, ".config"))
        return os.path.join(base_config_dir, "LxNotes", "recent_files.json")

    def _log(self, message, level="INFO"):
        """Pomocnicza funkcja wysyłająca logi do UI lub terminala"""
        if self.console and hasattr(self.console, 'log'):
            self.console.log(message, level)
        else:
            print(f"[{level}] {message}")
            log_message(level, message, "core.file.recent_files")

    def add_file(self, path):
        if not path or not isinstance(path, str):
            return

        path = os.path.abspath(path)

        with self._lock:
            if path in self.recent_files:
                self.recent_files.remove(path)

            self.recent_files.insert(0, path)

            if len(self.recent_files) > self.max_items:
                self.recent_files = self.recent_files[:self.max_items]

            self.save()

    def remove_file(self, path):
        path = os.path.abspath(path)
        with self._lock:
            if path in self.recent_files:
                self.recent_files.remove(path)
                self.save()
                self._log(f"Removed from history: {path}", "DEBUG")

    def get_files(self):
        return self.recent_files

    def save(self, force=False):
        with self._lock:
            snapshot = list(self.recent_files)
            if not force and snapshot == self._last_saved_state:
                return

            target_dir = os.path.dirname(self.config_path)
            os.makedirs(target_dir, exist_ok=True)
            tmp_path = None
            try:
                fd, tmp_path = tempfile.mkstemp(prefix="recent_files_", suffix=".tmp", dir=target_dir)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                os.replace(tmp_path, self.config_path)

                # Uprawnienia 600 na Linuksie (bezpieczenstwo danych uzytkownika)
                try:
                    os.chmod(self.config_path, 0o600)
                except Exception as e:
                    self._log(f"Could not set permissions on recent files config: {e}", "DEBUG")

                self._last_saved_state = snapshot
                self._log(f"Recent files list updated in {self.config_path}", "DEBUG")
            except Exception as e:
                self._log(f"Failed to save history: {e}", "ERROR")
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    def load(self):
        with self._lock:
            for candidate_path in (self.config_path, self.legacy_config_path):
                if not os.path.exists(candidate_path):
                    continue
                try:
                    with open(candidate_path, "r", encoding="utf-8") as f:
                        loaded_data = json.load(f)
                        if isinstance(loaded_data, list):
                            self.recent_files = [entry for entry in loaded_data if isinstance(entry, str) and entry]
                            self._last_saved_state = list(self.recent_files)
                            self._log(f"Loaded {len(self.recent_files)} recent files from history.", "SUCCESS")
                            if candidate_path == self.legacy_config_path and not os.path.exists(self.config_path):
                                self.save(force=True)
                            return
                        else:
                            self.recent_files = []
                            self._last_saved_state = []
                except Exception as e:
                    self._log(f"Error reading history file: {e}", "ERROR")
                    self.recent_files = []
                    self._last_saved_state = []
                    return

            self.recent_files = []
            self._last_saved_state = []
            self._log("No history file found. Creating new session.", "DEBUG")
