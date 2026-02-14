import os
import json

class RecentFiles:
    def __init__(self, console_logic=None, max_items=10):
        # Przechowujemy referencję do logiki konsoli
        self.console = console_logic
        self.max_items = max_items
        self.recent_files = []
        self.config_path = os.path.join(os.path.expanduser("~"), ".lxnotes_recent.json")
        self.load()

    def _log(self, message, level="INFO"):
        """Pomocnicza funkcja wysyłająca logi do UI lub terminala"""
        if self.console and hasattr(self.console, 'log'):
            self.console.log(message, level)
        else:
            print(f"[{level}] {message}")

    def add_file(self, path):
        if not path or not isinstance(path, str):
            return
            
        path = os.path.abspath(path)

        if path in self.recent_files:
            self.recent_files.remove(path)
        
        self.recent_files.insert(0, path)
        
        if len(self.recent_files) > self.max_items:
            self.recent_files = self.recent_files[:self.max_items]
        
        self.save()

    def remove_file(self, path):
        path = os.path.abspath(path)
        if path in self.recent_files:
            self.recent_files.remove(path)
            self.save()
            self._log(f"Removed from history: {path}", "DEBUG")

    def get_files(self):
        return self.recent_files

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.recent_files, f, ensure_ascii=False, indent=2)
            
            # Uprawnienia 600 na Linuksie (bezpieczeństwo danych użytkownika)
            try:
                os.chmod(self.config_path, 0o600)
            except:
                pass
                
            self._log(f"Recent files list updated in {self.config_path}", "DEBUG")
        except Exception as e:
            self._log(f"Failed to save history: {e}", "ERROR")

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, list):
                        self.recent_files = [f for f in loaded_data if f]
                        self._log(f"Loaded {len(self.recent_files)} recent files from history.", "SUCCESS")
                    else:
                        self.recent_files = []
            except Exception as e:
                self._log(f"Error reading history file: {e}", "ERROR")
                self.recent_files = []
        else:
            self.recent_files = []
            self._log("No history file found. Creating new session.", "DEBUG")