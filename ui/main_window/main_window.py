import json
import os
import sys
import webbrowser
import atexit
from pathlib import Path
from urllib.parse import quote
from core.logging import log_message

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QApplication, QMenu)
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence, QAction, QPalette
from PyQt6.QtCore import Qt

# --- Importy modułów LxNotes ---
from ui.menus.file_menu import FileMenu
from ui.menus.edit_menu import EditMenu
from ui.menus.info_menu import InfoMenu
from ui.menus.statusbar_menu import LxStatusBar
from core.editor.editor_manager import EditorManager
from core.theme.theme_manager import ThemeManager
from core.file.file_handler import FileHandler
from core.file.print_manager import PrintManager
from ui.dialogs.settings_dialog import SettingsDialog
from core.editor.language_handler import LanguageHandler
from core.editor.console_logic import ConsoleLogic
from ui.dialogs.console import ConsoleDialog

# Sprawdzenie silnika C++
try:
    import lx_engine
    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False

_ENGINE_LOGGER_ATEXIT_REGISTERED = False

class MainWindow(QMainWindow):
    def __init__(self, startup_logs=None, platform_manager=None):
        super().__init__()
        
        # --- 1. Konfiguracja i ścieżki ---
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.legacy_config_path = os.path.join(self.base_dir, "assets", "config.json")
        self.config_path = self._get_user_config_path()
        self.config = self.load_config()

        # --- 2. Inicjalizacja języka ---
        initial_lang = self.config.get("language", "system")
        self.lang_handler = LanguageHandler(self, config_lang=initial_lang)
        
        self.setWindowTitle("LxNotes")
        self.resize(1100, 750)

        # --- 3. Logika systemowa ---
        self.console_logic = ConsoleLogic(self)
        self.console_widget = None
        self.console_dialog = None  # compatibility alias used by older modules
        self.platform_manager = platform_manager
        self._init_systems(startup_logs)

        # --- 4. Managerowie ---
        self.editor_manager = EditorManager(self)
        self.theme_manager = ThemeManager(self)
        self.file_handler = FileHandler(self) # FileHandler korzysta z RecentFiles wewnętrznie
        self.print_manager = PrintManager(self)
        self.find_dialog = None

        # --- 5. Layout i UI ---
        self._setup_layout()
        self.init_ui()
        self.setup_global_shortcuts()
        
        # --- 6. Obsługa zdarzeń ---
        self.editor_manager.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.on_tab_changed()

        # --- 7. Finalizacja (Motyw, Teksty i Sesja) ---
        self._finalize_init()

    def _get_user_config_path(self):
        """Zwraca ścieżkę configu w katalogu użytkownika."""
        home_dir = str(Path.home())
        if sys.platform.startswith("win"):
            base_config_dir = os.getenv("APPDATA", home_dir)
        elif sys.platform == "darwin":
            base_config_dir = os.path.join(home_dir, "Library", "Application Support")
        else:
            base_config_dir = os.getenv("XDG_CONFIG_HOME", os.path.join(home_dir, ".config"))

        return os.path.join(base_config_dir, "LxNotes", "config.json")

    def load_config(self):
        """Wczytuje ustawienia użytkownika z katalogu profilu (z fallbackiem legacy)."""
        for path in (self.config_path, self.legacy_config_path):
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    # Jednorazowa migracja ze starej lokalizacji do user config dir.
                    if path == self.legacy_config_path and not os.path.exists(self.config_path):
                        self.save_config_data(config)
                    return config
                except (OSError, json.JSONDecodeError) as e:
                    print(f"Błąd wczytywania configu ({path}): {e}")
                    log_message("ERROR", f"Błąd wczytywania configu ({path}): {e}", "ui.main_window.main_window")
        return {"language": "system", "theme": "system", "last_session": []}

    def save_config(self):
        """Zapisuje aktualny stan do pliku config w katalogu użytkownika."""
        self.save_config_data(self.config)

    def save_config_data(self, config_data):
        """Zapisuje przekazane dane konfiguracyjne do docelowego pliku user config."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
        except OSError as e:
            if hasattr(self, 'console_logic'):
                self.console_logic.log(f"Nie udało się zapisać ustawień: {e}", "ERROR")

    def _init_systems(self, startup_logs):
        icon_path = os.path.join(self.base_dir, "assets", "icons", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        if ENGINE_AVAILABLE:
            try:
                lx_engine.set_logger(self.bridge_cpp_log)
                global _ENGINE_LOGGER_ATEXIT_REGISTERED
                if not _ENGINE_LOGGER_ATEXIT_REGISTERED and hasattr(lx_engine, "clear_logger"):
                    atexit.register(lx_engine.clear_logger)
                    _ENGINE_LOGGER_ATEXIT_REGISTERED = True
                self.console_logic.log("C++ Engine bridge established.", "SYSTEM")
            except Exception as e:
                self.console_logic.log(f"C++ Bridge failed: {e}", "ERROR")

        if startup_logs:
            for log in startup_logs: self.console_logic.log(log, "BOOT")

    def _setup_layout(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralWidget")
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_layout.addWidget(self.editor_manager.tab_widget)
        self.setCentralWidget(self.central_widget)

        self.custom_status_bar = LxStatusBar(self)
        self.setStatusBar(self.custom_status_bar)
        self.custom_status_bar.set_engine_status(ENGINE_AVAILABLE)

    def init_ui(self):
        self.menu_bar = self.menuBar()
        self.file_menu = FileMenu(self)
        self.menu_bar.addMenu(self.file_menu)
        self.edit_menu = EditMenu(self)
        self.menu_bar.addMenu(self.edit_menu)
        self.info_menu = InfoMenu(self)
        self.menu_bar.addMenu(self.info_menu)

        self.tools_menu = QMenu("Tools", self)
        self.menu_bar.addMenu(self.tools_menu)
        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self.open_settings)
        self.tools_menu.addAction(self.settings_action)

    def _finalize_init(self):
        """Ustawia motyw, odświeża napisy i przywraca sesję."""
        # 1. Rozpoznanie motywu
        theme_choice = self.config.get("theme", "system")
        if theme_choice == "system":
            is_dark = QPalette().color(QPalette.ColorRole.Window).lightness() < 128
            final_theme = "dark" if is_dark else "light"
        else:
            final_theme = theme_choice

        # 2. Aplikacja wyglądu
        self.theme_manager.apply_theme(final_theme)
        self.refresh_ui_texts()
        
        # 3. Przywracanie sesji
        last_session = self.config.get("last_session", [])
        if last_session:
            restored_count = 0
            for file_path in last_session:
                if os.path.exists(file_path):
                    # Wywołanie nowej metody z FileHandler
                    if self.file_handler.open_file_by_path(file_path):
                        restored_count += 1
            if restored_count > 0:
                self.console_logic.log(f"Session: Restoring {restored_count} files...", "SYSTEM")
        else:
            # Jeśli sesja pusta, otwórz pustą kartę
            if self.editor_manager.tab_widget.count() == 0:
                self.editor_manager.new_tab()

        if self.platform_manager: 
            self.platform_manager.apply_platform_tweaks(self)
            
        self.console_logic.log(f"LxNotes ready. Theme: {final_theme}", "SYSTEM")

    def refresh_ui_texts(self):
        tr = self.lang_handler.tr
        self.setWindowTitle(tr("window_title"))
        self.custom_status_bar.retranslate_ui()
        
        for menu in [self.file_menu, self.edit_menu, self.info_menu]:
            if hasattr(menu, 'retranslate_ui'): menu.retranslate_ui()

        self.tools_menu.setTitle(tr("menu_tools") if tr("menu_tools") != "menu_tools" else "Tools")
        self.settings_action.setText(tr("action_settings"))
        
        if self.find_dialog: self.find_dialog.retranslate_ui()
        if self.console_widget: self.console_widget.retranslate_ui()

    def open_settings(self):
        dialog = SettingsDialog(self, theme_manager=self.theme_manager)
        dialog.exec()

    def setup_global_shortcuts(self):
        self.console_shortcut = QShortcut(QKeySequence("F12"), self)
        self.console_shortcut.activated.connect(self.toggle_console)
        self.addAction(self.edit_menu.find_action)
        self.addAction(self.edit_menu.new_tab_action)
        self.addAction(self.edit_menu.close_tab_action)

    def on_tab_changed(self):
        self.setup_context_menu_for_current()
        if editor := self.editor_manager.get_current_editor():
            try:
                # Rozłączamy stare połączenia, by uniknąć duplikacji
                editor.cursorPositionChanged.disconnect()
                editor.textChanged.disconnect()
            except (TypeError, RuntimeError):
                pass
            editor.cursorPositionChanged.connect(self.custom_status_bar.update_info)
            editor.textChanged.connect(self.custom_status_bar.update_info)
            self.custom_status_bar.update_info()

    def show_find_replace(self):
        if self.find_dialog is None:
            from ui.dialogs.find_replace_dialog import FindReplaceDialog
            self.find_dialog = FindReplaceDialog(self, self.editor_manager)
        self.find_dialog.show()
        self.find_dialog.activateWindow()

    def toggle_console(self):
        if self.console_widget is None:
            self.console_widget = ConsoleDialog(self, self.console_logic)
            self.console_dialog = self.console_widget
        
        if self.console_widget.isVisible():
            self.console_widget.hide()
        else:
            self.console_widget.show()

    def print_current(self):
        if editor := self.editor_manager.get_current_editor():
            self.print_manager.print_editor(editor)

    def bridge_cpp_log(self, message: str, level: str):
        self.console_logic.log(message, level)

    def closeEvent(self, event):
        """Obsługa zamykania: sprawdzenie zapisu i zapamiętanie sesji."""
        if self.editor_manager.check_all_unsaved():
            
            # --- ZAPISYWANIE SESJI ---
            opened_files = []
            tab_widget = self.editor_manager.tab_widget
            for i in range(tab_widget.count()):
                editor = tab_widget.widget(i)
                file_path = getattr(editor, 'file_path', None)
                if file_path and os.path.exists(file_path):
                    opened_files.append(file_path)
            
            self.config["last_session"] = opened_files
            self.save_config()
            # --------------------------

            if self.find_dialog: self.find_dialog.close()
            if self.console_widget: self.console_widget.close()
            if hasattr(self, "console_logic"):
                self.console_logic.shutdown()
            if ENGINE_AVAILABLE and hasattr(lx_engine, "clear_logger"):
                try:
                    lx_engine.clear_logger()
                except Exception:
                    pass
            event.accept()
        else: 
            event.ignore()

    def setup_context_menu_for_current(self):
        if editor := self.editor_manager.get_current_editor():
            editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            try:
                editor.customContextMenuRequested.disconnect()
            except (TypeError, RuntimeError):
                pass
            editor.customContextMenuRequested.connect(self.show_custom_context_menu)

    def show_custom_context_menu(self, pos):
        editor = self.editor_manager.get_current_editor()
        if not editor: return
        menu = editor.createStandardContextMenu()
        selected_text = editor.textCursor().selectedText().strip()
        if selected_text:
            menu.addSeparator()
            search_action = QAction(f"Search Google: '{selected_text[:15]}...'", self)
            search_action.triggered.connect(lambda: webbrowser.open(f"https://google.com/search?q={quote(selected_text)}"))
            menu.addAction(search_action)
        menu.exec(editor.mapToGlobal(pos))
