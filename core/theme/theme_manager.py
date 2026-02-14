import os
from PyQt6.QtWidgets import QApplication
from core.logging import log_message

class ThemeManager:
    def __init__(self, main_window, console_logic=None):
        self.main_window = main_window
        self.console = console_logic
        self.current_theme = "light"

        # Dynamiczne szukanie korzenia projektu
        current_file_path = os.path.abspath(__file__)
        project_root = os.path.dirname(current_file_path)
        
        while project_root != os.path.dirname(project_root):
            if os.path.exists(os.path.join(project_root, "assets")):
                break
            project_root = os.path.dirname(project_root)

        self.styles_path = os.path.join(project_root, "assets", "styles")
        self._log(f"Styles directory detected: {self.styles_path}", "DEBUG")

    def _log(self, message, level="INFO"):
        """Logowanie do konsoli UI lub terminala"""
        if self.console and hasattr(self.console, 'log'):
            self.console.log(message, level)
        else:
            print(f"[{level}] {message}")
            log_message(level, message, "core.theme.theme_manager")

    def apply_theme(self, theme_name):
        theme_name = theme_name.lower()
        if theme_name not in ["light", "dark"]:
            theme_name = "light"

        style_file = os.path.join(self.styles_path, f"{theme_name}.qss")

        try:
            if not os.path.exists(style_file):
                self._log(f"QSS file missing: {style_file}", "ERROR")
                return

            with open(style_file, "r", encoding="utf-8") as f:
                qss = f.read()
            
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss)
                self.current_theme = theme_name
                self._log(f"Theme '{theme_name}' applied successfully.", "SUCCESS")
            else:
                self._log("QApplication instance not found!", "ERROR")
            
        except Exception as e:
            self._log(f"Critical error loading theme: {e}", "ERROR")

    def toggle_theme(self):
        """Szybka zmiana motywu na przeciwny"""
        new_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme(new_theme)
