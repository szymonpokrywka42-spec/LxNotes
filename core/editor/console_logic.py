import os
import datetime
import time
import platform
import sys
import subprocess
import threading
from core.logging import log_message, flush_runtime_logs

class ConsoleLogic:
    COMMAND_DOCS = {
        "help": {
            "usage": "help [command]",
            "description": "Show available commands or detailed help for one command.",
            "examples": ["help", "help open"],
            "aliases": [],
        },
        "clear": {
            "usage": "clear",
            "description": "Clear console output window.",
            "examples": ["clear"],
            "aliases": [],
        },
        "save": {
            "usage": "save",
            "description": "Save current file in active tab.",
            "examples": ["save"],
            "aliases": [],
        },
        "save-all": {
            "usage": "save-all",
            "description": "Run the Save All workflow for modified files, if available.",
            "examples": ["save-all"],
            "aliases": [],
        },
        "open": {
            "usage": "open <path>",
            "description": "Open file by absolute or relative path.",
            "examples": ["open notes.txt", "open /home/user/work/todo.md"],
            "aliases": [],
        },
        "recent": {
            "usage": "recent",
            "description": "List recent files with numbering.",
            "examples": ["recent"],
            "aliases": [],
        },
        "open-recent": {
            "usage": "open-recent <n>",
            "description": "Open the n-th file from recent files.",
            "examples": ["open-recent 1"],
            "aliases": [],
        },
        "logs": {
            "usage": "logs",
            "description": "Open logs directory in system file manager.",
            "examples": ["logs"],
            "aliases": [],
        },
        "sys": {
            "usage": "sys",
            "description": "Show basic runtime environment info.",
            "examples": ["sys"],
            "aliases": ["sys-info"],
        },
        "crash": {
            "usage": "crash",
            "description": "Run controlled crash-test path and log handled error.",
            "examples": ["crash"],
            "aliases": [],
        },
        "turbo": {
            "usage": "turbo [on|off|status]",
            "description": "Inspect or switch Turbo mode status.",
            "examples": ["turbo", "turbo on", "turbo off"],
            "aliases": [],
        },
        "exit": {
            "usage": "exit",
            "description": "Close application window.",
            "examples": ["exit"],
            "aliases": [],
        },
    }

    COMMAND_ALIASES = {
        "sys-info": "sys",
    }

    def __init__(self, main_window):
        self.main_window = main_window
        self.history = []
        self.command_history = []  # Historia wpisanych komend (dla strzałek)
        self._file_lock = threading.Lock()
        self._pending_log_writes = 0
        self._last_log_sync = time.monotonic()
        self._log_sync_interval = 0.25
        self._log_sync_every = 25
        
        # 1. Konfiguracja ścieżek
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.logs_dir = os.path.join(base_dir, "assets", "logs")
        
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
            
        self.log_file = os.path.join(self.logs_dir, f"log_{datetime.datetime.now().strftime('%Y-%m-%d')}.log")
        self._log_fp = open(self.log_file, "a", encoding="utf-8", buffering=1)
        
        # 2. Czyszczenie starych logów (> 48h)
        self.cleanup_old_logs(hours=48)
        self.log("Console Logic Initialized", "SYSTEM")

    def _tr(self, key, default):
        lang_handler = getattr(self.main_window, "lang_handler", None)
        if lang_handler and hasattr(lang_handler, "tr"):
            text = lang_handler.tr(key)
            if text != key:
                return text
        return default

    def log(self, message, level="INFO"):
        """Główna funkcja logująca."""
        now = datetime.datetime.now()
        timestamp = now.strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] [{level}] {message}"
        
        self.history.append(formatted_msg)
        log_message(level, message, "console")
        
        # Przekazanie do UI (jeśli otwarte)
        console_ui = None
        if hasattr(self.main_window, "console_widget") and self.main_window.console_widget:
            console_ui = self.main_window.console_widget
        elif hasattr(self.main_window, "console_dialog") and self.main_window.console_dialog:
            # Backward compatibility with older attribute name.
            console_ui = self.main_window.console_dialog

        if console_ui:
            try:
                console_ui.append_text(formatted_msg, level)
            except Exception as e:
                print(f"[WARN] Console UI append failed: {type(e).__name__}: {e}")
        
        print(formatted_msg)
        self._write_to_disk(formatted_msg)

    def _write_to_disk(self, text):
        try:
            with self._file_lock:
                self._log_fp.write(text + "\n")
                self._pending_log_writes += 1
                self._flush_log_file_if_needed()
        except Exception as e:
            print(f"Log Save Error: {e}")

    def _flush_log_file_if_needed(self, force=False):
        if not self._log_fp:
            return

        now = time.monotonic()
        if not force:
            if self._pending_log_writes <= 0:
                return
            if self._pending_log_writes < self._log_sync_every and (now - self._last_log_sync) < self._log_sync_interval:
                return

        self._log_fp.flush()
        os.fsync(self._log_fp.fileno())
        self._pending_log_writes = 0
        self._last_log_sync = now
        flush_runtime_logs()

    def cleanup_old_logs(self, hours=48):
        try:
            now = time.time()
            cutoff = now - (hours * 3600)
            if os.path.exists(self.logs_dir):
                for filename in os.listdir(self.logs_dir):
                    file_path = os.path.join(self.logs_dir, filename)
                    if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff:
                        os.remove(file_path)
        except Exception as e:
            self.log(f"Cleanup Error: {e}", "ERROR")

    def _help_overview_text(self):
        lines = [self._tr("console_help_available_commands", "Available commands:")]
        for name in sorted(self.COMMAND_DOCS.keys()):
            doc = self.COMMAND_DOCS[name]
            aliases = doc.get("aliases", [])
            alias_text = f" (aliases: {', '.join(aliases)})" if aliases else ""
            lines.append(f"- {doc['usage']}: {doc['description']}{alias_text}")
        lines.append(self._tr("console_help_tip", "Tip: use 'help <command>' for details."))
        return "\n".join(lines)

    def _help_for_command_text(self, name):
        canonical = self.COMMAND_ALIASES.get(name, name)
        doc = self.COMMAND_DOCS.get(canonical)
        if not doc:
            template = self._tr(
                "console_help_no_entry",
                "No help entry for '{name}'. Type 'help' to list commands.",
            )
            return template.format(name=name)

        lines = [
            f"{self._tr('console_help_command', 'Command')}: {canonical}",
            f"{self._tr('console_help_usage', 'Usage')}: {doc['usage']}",
            f"{self._tr('console_help_description', 'Description')}: {doc['description']}",
        ]
        aliases = doc.get("aliases", [])
        if aliases:
            lines.append(f"{self._tr('console_help_aliases', 'Aliases')}: {', '.join(aliases)}")
        examples = doc.get("examples", [])
        if examples:
            lines.append(f"{self._tr('console_help_examples', 'Examples')}:")
            for ex in examples:
                lines.append(f"- {ex}")
        return "\n".join(lines)

    def _get_recent_files(self):
        file_handler = getattr(self.main_window, "file_handler", None)
        recent_source = getattr(file_handler, "recent_files", None) if file_handler else None
        if recent_source is None:
            recent_source = getattr(self.main_window, "recent_files", None)

        if recent_source is None:
            return []

        try:
            if hasattr(recent_source, "get_files"):
                files = recent_source.get_files()
            elif isinstance(recent_source, (list, tuple)):
                files = list(recent_source)
            else:
                files = getattr(recent_source, "recent_files", [])
        except Exception:
            return []

        return [path for path in files if isinstance(path, str) and path]

    def _get_unsaved_editors(self):
        editor_manager = getattr(self.main_window, "editor_manager", None)
        if not editor_manager or not hasattr(editor_manager, "get_all_editors"):
            return []

        unsaved = []
        try:
            editors = editor_manager.get_all_editors()
        except Exception:
            return []

        for editor in editors:
            try:
                document = editor.document() if hasattr(editor, "document") else None
                if document and hasattr(document, "isModified") and document.isModified():
                    unsaved.append(editor)
            except Exception:
                continue
        return unsaved

    def _format_save_all_result(self, result, available=True):
        if result is True:
            return self._tr("console_cmd_save_all_done", "Save All completed.")
        if result is False:
            return self._tr("console_cmd_save_all_failed", "Save All was canceled or failed.")
        if result is None and available:
            return self._tr("console_cmd_save_all_triggered", "Save All workflow started.")
        return self._tr("console_cmd_save_all_unavailable", "Save All workflow is not available.")

    def _run_save_all_workflow(self):
        file_handler = getattr(self.main_window, "file_handler", None)
        editor_manager = getattr(self.main_window, "editor_manager", None)

        workflow = None
        workflow_owner = None
        if file_handler is not None:
            for name in ("save_all_workflow", "save_all", "save_all_sequence"):
                candidate = getattr(file_handler, name, None)
                if callable(candidate):
                    workflow = candidate
                    workflow_owner = name
                    break

        if workflow is None and editor_manager is not None:
            for name in ("save_all_workflow", "save_all", "save_all_sequence"):
                candidate = getattr(editor_manager, name, None)
                if callable(candidate):
                    workflow = candidate
                    workflow_owner = name
                    break

        if workflow is None:
            return self._format_save_all_result(None, available=False)

        try:
            if workflow_owner == "save_all_sequence":
                result = workflow(self._get_unsaved_editors())
            else:
                result = workflow()
        except TypeError:
            if workflow_owner == "save_all_sequence":
                result = workflow(self._get_unsaved_editors())
            else:
                raise
        except Exception as e:
            self.log(f"Save All failed: {e}", "ERROR")
            template = self._tr("console_cmd_save_all_error", "Save All failed: {error}")
            return template.format(error=e)
        return self._format_save_all_result(result)

    def _format_recent_files_text(self):
        files = self._get_recent_files()
        if not files:
            return self._tr("console_cmd_recent_empty", "No recent files.")

        lines = [self._tr("console_cmd_recent_header", "Recent files:")]
        for index, path in enumerate(files, start=1):
            lines.append(f"{index}. {path}")
        return "\n".join(lines)

    def _open_recent_file(self, index_text):
        try:
            index = int(index_text)
        except (TypeError, ValueError):
            template = self._tr(
                "console_cmd_open_recent_invalid",
                "Invalid recent file number: {index}. Use 'recent' to list files.",
            )
            return template.format(index=index_text)

        files = self._get_recent_files()
        if index < 1 or index > len(files):
            template = self._tr(
                "console_cmd_open_recent_out_of_range",
                "Recent file number {index} is out of range. Use 'recent' to list files.",
            )
            return template.format(index=index)

        path = files[index - 1]
        file_handler = getattr(self.main_window, "file_handler", None)
        opener = getattr(file_handler, "open_file", None) if file_handler else None
        if not callable(opener):
            return self._tr(
                "console_cmd_open_recent_unavailable",
                "Open recent is not available.",
            )

        try:
            opener(path)
        except Exception as e:
            self.log(f"Open recent failed: {e}", "ERROR")
            template = self._tr("console_cmd_open_recent_error", "Open recent failed: {error}")
            return template.format(error=e)
        template = self._tr("console_cmd_opening_recent", "Opening recent file: {path}")
        return template.format(path=path)

    def execute_command(self, cmd_text):
        """Parser komend terminala."""
        full_cmd = cmd_text.strip()
        if not full_cmd: return None
        
        self.command_history.append(full_cmd)
        parts = full_cmd.split()
        raw_cmd = parts[0].lower()
        cmd = self.COMMAND_ALIASES.get(raw_cmd, raw_cmd)
        args = parts[1:] if len(parts) > 1 else []

        self.log(f"> {full_cmd}", "ACTION")

        # Tablica komend dla przejrzystości
        if cmd == "clear":
            return "clear"
            
        elif cmd == "help":
            if args:
                return self._help_for_command_text(args[0].lower())
            return self._help_overview_text()

        elif cmd == "save":
            self.main_window.file_handler.save_file()
            return self._tr("console_cmd_file_saved", "File saved.")

        elif cmd == "save-all":
            return self._run_save_all_workflow()

        elif cmd == "exit":
            self.main_window.close()
            return self._tr("console_cmd_closing", "Closing...")

        elif cmd == "logs":
            try:
                if sys.platform.startswith("win"):
                    subprocess.Popen(["explorer", self.logs_dir])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", self.logs_dir])
                else:
                    subprocess.Popen(["xdg-open", self.logs_dir])
                return self._tr("console_cmd_opening_logs", "Opening logs folder...")
            except Exception as e:
                self.log(f"Failed to open logs folder: {e}", "ERROR")
                template = self._tr(
                    "console_cmd_logs_open_failed",
                    "Cannot open logs folder automatically. Path: {path}",
                )
                return template.format(path=self.logs_dir)

        elif cmd == "sys":
            return (f"OS: {platform.system()} | Py: {sys.version.split()[0]} | "
                    f"Arch: {platform.machine()}")

        elif cmd == "crash":
            self.log("Manual crash test triggered.", "WARN")
            try:
                _ = 1 / 0
            except ZeroDivisionError as e:
                self.log(f"Intercepted: {e}", "ERROR")
                return self._tr("console_cmd_error_logged", "Error logged successfully.")

        elif cmd == "turbo":
            state = args[0] if args else "status"
            if state == "on":
                # Tutaj w przyszłości: import lx_engine; lx_engine.set_turbo(True)
                return self._tr("console_cmd_turbo_enabled", "Turbo Mode: ENABLED (C++ Engine Active)")
            elif state == "off":
                return self._tr("console_cmd_turbo_disabled", "Turbo Mode: DISABLED (Standard Mode)")
            return self._tr("console_cmd_turbo_auto", "Turbo Mode is currently: AUTOMATIC")

        elif cmd == "open":
            if args:
                path = " ".join(args)
                self.main_window.file_handler.open_file(path)
                template = self._tr("console_cmd_opening", "Opening: {path}")
                return template.format(path=path)
            return self._tr("console_cmd_open_path_required", "Error: Path required.")

        elif cmd == "recent":
            return self._format_recent_files_text()

        elif cmd == "open-recent":
            if not args:
                return self._tr(
                    "console_cmd_open_recent_required",
                    "Error: Recent file number required.",
                )
            return self._open_recent_file(args[0])

        else:
            template = self._tr("console_cmd_unknown", "Unknown command: {cmd}. Type 'help' for info.")
            return template.format(cmd=raw_cmd)

    def shutdown(self):
        try:
            with self._file_lock:
                self._flush_log_file_if_needed(force=True)
                self._log_fp.close()
        except Exception as e:
            print(f"[WARN] Console shutdown flush skipped: {type(e).__name__}: {e}")
        flush_runtime_logs(force=True)
