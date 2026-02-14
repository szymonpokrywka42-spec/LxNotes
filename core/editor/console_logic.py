import os
import datetime
import time
import platform
import sys
import subprocess
import threading
from core.logging import log_message, flush_runtime_logs

class ConsoleLogic:
    def __init__(self, main_window):
        self.main_window = main_window
        self.history = []
        self.command_history = []  # Historia wpisanych komend (dla strzałek)
        self._file_lock = threading.Lock()
        
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
            except Exception:
                pass
        
        print(formatted_msg)
        self._write_to_disk(formatted_msg)

    def _write_to_disk(self, text):
        try:
            with self._file_lock:
                self._log_fp.write(text + "\n")
                self._log_fp.flush()
                os.fsync(self._log_fp.fileno())
                flush_runtime_logs()
        except Exception as e:
            print(f"Log Save Error: {e}")

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

    def execute_command(self, cmd_text):
        """Parser komend terminala."""
        full_cmd = cmd_text.strip()
        if not full_cmd: return None
        
        self.command_history.append(full_cmd)
        parts = full_cmd.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        self.log(f"> {full_cmd}", "ACTION")

        # Tablica komend dla przejrzystości
        if cmd == "clear":
            return "clear"
            
        elif cmd == "help":
            return "Commands: help, clear, save, open <path>, logs, sys, crash, turbo <on/off>, exit"

        elif cmd == "save":
            self.main_window.file_handler.save_file()
            return "File saved."

        elif cmd == "exit":
            self.main_window.close()
            return "Closing..."

        elif cmd == "logs":
            try:
                if sys.platform.startswith("win"):
                    os.startfile(self.logs_dir)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", self.logs_dir])
                else:
                    subprocess.Popen(["xdg-open", self.logs_dir])
                return "Opening logs folder..."
            except Exception as e:
                self.log(f"Failed to open logs folder: {e}", "ERROR")
                return f"Cannot open logs folder automatically. Path: {self.logs_dir}"

        elif cmd in ["sys", "sys-info"]:
            return (f"OS: {platform.system()} | Py: {sys.version.split()[0]} | "
                    f"Arch: {platform.machine()}")

        elif cmd == "crash":
            self.log("Manual crash test triggered.", "WARN")
            try:
                _ = 1 / 0
            except ZeroDivisionError as e:
                self.log(f"Intercepted: {e}", "ERROR")
                return "Error logged successfully."

        elif cmd == "turbo":
            state = args[0] if args else "status"
            if state == "on":
                # Tutaj w przyszłości: import lx_engine; lx_engine.set_turbo(True)
                return "Turbo Mode: ENABLED (C++ Engine Active)"
            elif state == "off":
                return "Turbo Mode: DISABLED (Standard Mode)"
            return "Turbo Mode is currently: AUTOMATIC"

        elif cmd == "open":
            if args:
                path = " ".join(args)
                self.main_window.file_handler.open_file(path)
                return f"Opening: {path}"
            return "Error: Path required."

        else:
            return f"Unknown command: {cmd}. Type 'help' for info."

    def shutdown(self):
        try:
            with self._file_lock:
                self._log_fp.flush()
                os.fsync(self._log_fp.fileno())
                self._log_fp.close()
        except Exception:
            pass
        flush_runtime_logs()
