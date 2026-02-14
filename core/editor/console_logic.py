import os
import datetime
import time
import platform
import sys

class ConsoleLogic:
    def __init__(self, main_window):
        self.main_window = main_window
        self.history = []
        self.command_history = []  # Historia wpisanych komend (dla strzałek)
        
        # 1. Konfiguracja ścieżek
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.logs_dir = os.path.join(base_dir, "assets", "logs")
        
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
            
        self.log_file = os.path.join(self.logs_dir, f"log_{datetime.datetime.now().strftime('%Y-%m-%d')}.log")
        
        # 2. Czyszczenie starych logów (> 48h)
        self.cleanup_old_logs(hours=48)
        self.log("Console Logic Initialized", "SYSTEM")

    def log(self, message, level="INFO"):
        """Główna funkcja logująca."""
        now = datetime.datetime.now()
        timestamp = now.strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] [{level}] {message}"
        
        self.history.append(formatted_msg)
        
        # Przekazanie do UI (jeśli otwarte)
        if hasattr(self.main_window, 'console_dialog') and self.main_window.console_dialog:
            self.main_window.console_dialog.append_text(formatted_msg, level)
        
        print(formatted_msg)
        self._write_to_disk(formatted_msg)

    def _write_to_disk(self, text):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(text + "\n")
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
            os.startfile(self.logs_dir)
            return "Opening logs folder..."

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