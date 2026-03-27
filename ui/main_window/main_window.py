import json
import os
import sys
import webbrowser
import atexit
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from core.logging import log_message

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QApplication, QMenu, QInputDialog)
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence, QAction, QPalette
from PyQt6.QtCore import Qt, QTimer

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
from ui.dialogs.quick_open_dialog import QuickOpenDialog

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
        self._pending_snapshot_states = {}
        self._pending_snapshot_active_path = None
        self._pending_snapshot_retries = 0
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

    def _tr(self, key, default):
        tr = self.lang_handler.tr if hasattr(self, "lang_handler") else (lambda x: x)
        value = tr(key)
        return default if value == key else value

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
                    config_changed = False

                    # Automatyczna migracja do nowego klucza statusbara.
                    if "status_bar_mode" not in config:
                        legacy_flag = config.get("advanced_status_bar")
                        if isinstance(legacy_flag, bool):
                            config["status_bar_mode"] = "advanced" if legacy_flag else "simple"
                        else:
                            config["status_bar_mode"] = "simple"
                        config_changed = True

                    if "save_encoding_policy" not in config:
                        config["save_encoding_policy"] = "preserve"
                        config_changed = True

                    # Legacy compatibility: trzymaj także bool dla starszych ścieżek kodu.
                    expected_legacy = config.get("status_bar_mode") == "advanced"
                    if config.get("advanced_status_bar") is not expected_legacy:
                        config["advanced_status_bar"] = expected_legacy
                        config_changed = True
                    # Jednorazowa migracja ze starej lokalizacji do user config dir.
                    if path == self.legacy_config_path and not os.path.exists(self.config_path):
                        self.save_config_data(config)
                    elif config_changed:
                        # Nadpisujemy config po migracji, by kolejne uruchomienia były spójne.
                        self.save_config_data(config)
                    return config
                except (OSError, json.JSONDecodeError) as e:
                    print(f"Błąd wczytywania configu ({path}): {e}")
                    log_message("ERROR", f"Błąd wczytywania configu ({path}): {e}", "ui.main_window.main_window")
        return {
            "language": "system",
            "theme": "system",
            "status_bar_mode": "simple",
            "save_encoding_policy": "preserve",
            "last_session": [],
        }

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
        self._statusbar_update_timer = QTimer(self)
        self._statusbar_update_timer.setSingleShot(True)
        self._statusbar_update_timer.setInterval(80)
        self._statusbar_update_timer.timeout.connect(self.custom_status_bar.update_info)
        self.apply_status_bar_mode(self.get_configured_status_bar_mode())

    def get_configured_status_bar_mode(self):
        mode = self.config.get("status_bar_mode")
        if isinstance(mode, str) and mode.lower() in {"simple", "advanced"}:
            return mode.lower()
        legacy = self.config.get("advanced_status_bar")
        if isinstance(legacy, bool):
            return "advanced" if legacy else "simple"
        return "simple"

    def apply_status_bar_mode(self, mode):
        normalized_mode = "advanced" if str(mode).lower() == "advanced" else "simple"
        self.config["status_bar_mode"] = normalized_mode
        # Legacy compatibility for any external code still expecting bool config.
        self.config["advanced_status_bar"] = normalized_mode == "advanced"
        if hasattr(self, "custom_status_bar") and self.custom_status_bar:
            self.custom_status_bar.set_display_mode(normalized_mode)
            self.custom_status_bar.update_info()

    def _update_statusbar_now(self):
        if hasattr(self, "_statusbar_update_timer") and self._statusbar_update_timer:
            self._statusbar_update_timer.stop()
        if hasattr(self, "custom_status_bar") and self.custom_status_bar:
            self.custom_status_bar.update_info()

    def _schedule_statusbar_update(self):
        if hasattr(self, "_statusbar_update_timer") and self._statusbar_update_timer:
            self._statusbar_update_timer.start()
        elif hasattr(self, "custom_status_bar") and self.custom_status_bar:
            self.custom_status_bar.update_info()

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

        self.quick_open_action = QAction("Quick Open...", self)
        self.quick_open_action.setShortcut(QKeySequence("Ctrl+P"))
        self.quick_open_action.triggered.connect(self.show_quick_open)
        self.tools_menu.addAction(self.quick_open_action)

        self.tools_menu.addSeparator()
        self.save_snapshot_action = QAction(self._tr("action_save_session_snapshot", "Save Session Snapshot"), self)
        self.save_snapshot_action.setShortcut(QKeySequence("Ctrl+Alt+S"))
        self.save_snapshot_action.triggered.connect(self.save_session_snapshot)
        self.tools_menu.addAction(self.save_snapshot_action)

        self.restore_snapshot_action = QAction(
            self._tr("action_restore_session_snapshot", "Restore Session Snapshot..."), self
        )
        self.restore_snapshot_action.setShortcut(QKeySequence("Ctrl+Alt+R"))
        self.restore_snapshot_action.triggered.connect(self.restore_session_snapshot_interactive)
        self.tools_menu.addAction(self.restore_snapshot_action)

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
        last_session_state = self.config.get("last_session_state")
        if isinstance(last_session_state, dict):
            restored_count = self._restore_session_state(last_session_state, check_unsaved=False)
            if restored_count > 0:
                self.console_logic.log(f"Session: Restoring snapshot with {restored_count} files...", "SYSTEM")
        elif last_session:
            restored_count = 0
            for file_path in last_session:
                if os.path.exists(file_path):
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
        quick_open_text = tr("action_quick_open")
        self.quick_open_action.setText(quick_open_text if quick_open_text != "action_quick_open" else "Quick Open...")
        save_snapshot_text = tr("action_save_session_snapshot")
        self.save_snapshot_action.setText(
            save_snapshot_text if save_snapshot_text != "action_save_session_snapshot" else "Save Session Snapshot"
        )
        restore_snapshot_text = tr("action_restore_session_snapshot")
        self.restore_snapshot_action.setText(
            restore_snapshot_text if restore_snapshot_text != "action_restore_session_snapshot" else "Restore Session Snapshot..."
        )
        
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
        self.addAction(self.edit_menu.reopen_tab_action)
        self.addAction(self.edit_menu.load_full_editable_action)
        self.addAction(self.edit_menu.next_chunk_action)
        self.addAction(self.edit_menu.prev_chunk_action)
        self.addAction(self.edit_menu.quick_revert_safe_action)
        self.addAction(self.quick_open_action)
        self.addAction(self.file_menu.save_all_action)
        self.addAction(self.save_snapshot_action)
        self.addAction(self.restore_snapshot_action)

    def on_tab_changed(self):
        self.setup_context_menu_for_current()
        if editor := self.editor_manager.get_current_editor():
            # Rozłączamy tylko nasze sloty, żeby uniknąć duplikacji po wielokrotnych
            # przełączeniach kart i nie naruszać cudzych połączeń sygnałów.
            for signal, slot in (
                (editor.cursorPositionChanged, self._schedule_statusbar_update),
                (editor.textChanged, self._schedule_statusbar_update),
                (editor.cursorPositionChanged, self.edit_menu.update_menu_states),
                (editor.selectionChanged, self.edit_menu.update_menu_states),
                (editor.textChanged, self.edit_menu.update_menu_states),
            ):
                try:
                    signal.disconnect(slot)
                except (TypeError, RuntimeError):
                    continue
            editor.cursorPositionChanged.connect(self._schedule_statusbar_update)
            editor.textChanged.connect(self._schedule_statusbar_update)
            editor.cursorPositionChanged.connect(self.edit_menu.update_menu_states)
            editor.selectionChanged.connect(self.edit_menu.update_menu_states)
            editor.textChanged.connect(self.edit_menu.update_menu_states)
            self._try_apply_pending_snapshot_state(editor)
            self._update_statusbar_now()
            self.edit_menu.update_menu_states()

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

    def _collect_quick_open_files(self):
        paths = []
        for path in self.file_handler.recent_files.get_files():
            if isinstance(path, str) and os.path.exists(path):
                paths.append(path)

        seen = set(paths)
        for editor in self.editor_manager.get_all_editors():
            file_path = getattr(editor, "file_path", "")
            if file_path and os.path.exists(file_path) and file_path not in seen:
                paths.append(file_path)
                seen.add(file_path)
        return paths

    def show_quick_open(self):
        files = self._collect_quick_open_files()
        if not files:
            self.console_logic.log("Quick Open: no files in history.", "INFO")
            return

        dialog = QuickOpenDialog(self, files=files)
        if dialog.exec():
            selected_path = dialog.selected_path()
            if selected_path:
                self.file_handler.open_file(selected_path)

    def bridge_cpp_log(self, message: str, level: str):
        self.console_logic.log(message, level)

    def _collect_session_state(self):
        tab_widget = self.editor_manager.tab_widget
        tabs = []
        active_idx = tab_widget.currentIndex()
        active_path = None

        for idx in range(tab_widget.count()):
            editor = tab_widget.widget(idx)
            file_path = getattr(editor, "file_path", None)
            if not file_path or not os.path.exists(file_path):
                continue
            cursor_pos = 0
            scroll_value = 0
            try:
                cursor_pos = int(editor.textCursor().position())
            except Exception:
                cursor_pos = 0
            try:
                scroll_value = int(editor.verticalScrollBar().value())
            except Exception:
                scroll_value = 0
            entry = {
                "file_path": file_path,
                "cursor_position": max(0, cursor_pos),
                "scroll_value": max(0, scroll_value),
            }
            tabs.append(entry)
            if idx == active_idx:
                active_path = file_path
        return {
            "name": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "tabs": tabs,
            "active_path": active_path,
        }

    def save_session_snapshot(self):
        state = self._collect_session_state()
        tabs = state.get("tabs", [])
        if not tabs:
            self.console_logic.log(
                self._tr("session_snapshot_skipped_no_files", "Snapshot skipped: no file-backed tabs."),
                "INFO",
            )
            return
        snapshots = self.config.get("session_snapshots", [])
        if not isinstance(snapshots, list):
            snapshots = []
        snapshots.append(state)
        snapshots = snapshots[-15:]
        self.config["session_snapshots"] = snapshots
        self.save_config()
        self.console_logic.log(
            self._tr("session_snapshot_saved", "Session snapshot saved ({count} tabs).").format(count=len(tabs)),
            "SUCCESS",
        )
        self.statusBar().showMessage(
            self._tr("session_snapshot_saved_named", "Session snapshot saved: {name}").format(name=state["name"]),
            3000,
        )

    def restore_session_snapshot_interactive(self):
        snapshots = self.config.get("session_snapshots", [])
        if not isinstance(snapshots, list) or not snapshots:
            self.console_logic.log(self._tr("session_snapshot_none", "No session snapshots available."), "INFO")
            return

        labels = []
        for idx, snap in enumerate(snapshots):
            name = snap.get("name", f"Snapshot {idx + 1}")
            tabs_count = len(snap.get("tabs", [])) if isinstance(snap.get("tabs", []), list) else 0
            labels.append(f"{name} ({tabs_count} tabs)")

        selected_label, ok = QInputDialog.getItem(
            self,
            self._tr("session_snapshot_restore_title", "Restore Session Snapshot"),
            self._tr("session_snapshot_restore_prompt", "Choose snapshot:"),
            labels,
            len(labels) - 1,
            False,
        )
        if not ok:
            return
        selected_idx = labels.index(selected_label)
        self._restore_session_state(snapshots[selected_idx], check_unsaved=True)

    def _restore_session_state(self, state, check_unsaved):
        tabs_state = state.get("tabs", []) if isinstance(state, dict) else []
        if not isinstance(tabs_state, list):
            return 0

        valid_tabs = [t for t in tabs_state if isinstance(t, dict) and os.path.exists(str(t.get("file_path", "")))]
        if not valid_tabs:
            self.console_logic.log(
                self._tr("session_snapshot_restore_skipped", "Snapshot restore skipped: no valid files."),
                "WARN",
            )
            return 0

        if check_unsaved and not self.editor_manager.check_all_unsaved():
            self.console_logic.log(self._tr("session_snapshot_restore_canceled", "Snapshot restore canceled."), "INFO")
            return 0

        self._clear_all_tabs_for_restore()

        self._pending_snapshot_states = {}
        for tab_state in valid_tabs:
            path = str(tab_state.get("file_path", ""))
            self._pending_snapshot_states.setdefault(path, []).append(tab_state)

        self._pending_snapshot_active_path = state.get("active_path")
        self._pending_snapshot_retries = 16

        restored_count = 0
        for tab_state in valid_tabs:
            path = str(tab_state.get("file_path", ""))
            if self.file_handler.open_file_by_path(path):
                restored_count += 1

        self._schedule_pending_snapshot_apply()
        if restored_count > 0:
            self.console_logic.log(
                self._tr("session_snapshot_restore_started", "Session snapshot restore started ({count} files).").format(
                    count=restored_count
                ),
                "SYSTEM",
            )
        return restored_count

    def _clear_all_tabs_for_restore(self):
        tab_widget = self.editor_manager.tab_widget
        while tab_widget.count() > 0:
            editor = tab_widget.widget(0)
            if getattr(editor, "large_file_mode", False) and hasattr(editor, "disable_large_file_mode"):
                editor.disable_large_file_mode()
            tab_widget.removeTab(0)
        if tab_widget.count() == 0:
            self.editor_manager.new_tab()
            tab_widget.removeTab(0)

    def _schedule_pending_snapshot_apply(self):
        QTimer.singleShot(220, self._pump_pending_snapshot_restore)

    def _pump_pending_snapshot_restore(self):
        if not self._pending_snapshot_states:
            return
        self._pending_snapshot_retries -= 1
        for editor in self.editor_manager.get_all_editors():
            self._try_apply_pending_snapshot_state(editor)
        if self._pending_snapshot_states and self._pending_snapshot_retries > 0:
            self._schedule_pending_snapshot_apply()
        elif self._pending_snapshot_states:
            self.console_logic.log(
                self._tr(
                    "session_snapshot_restore_partial",
                    "Snapshot restore finished with partial cursor/scroll restore.",
                ),
                "WARN",
            )
            self._pending_snapshot_states = {}
            self._pending_snapshot_active_path = None
        else:
            self._pending_snapshot_active_path = None

    def _try_apply_pending_snapshot_state(self, editor):
        file_path = str(getattr(editor, "file_path", "") or "")
        if not file_path or file_path not in self._pending_snapshot_states:
            return
        states = self._pending_snapshot_states[file_path]
        if not states:
            self._pending_snapshot_states.pop(file_path, None)
            return
        state = states.pop(0)
        if not states:
            self._pending_snapshot_states.pop(file_path, None)

        if not getattr(editor, "large_file_mode", False):
            try:
                cursor_pos = int(state.get("cursor_position", 0))
                cursor = editor.textCursor()
                cursor.setPosition(max(0, min(cursor_pos, editor.document().characterCount() - 1)))
                editor.setTextCursor(cursor)
            except Exception as e:
                self.console_logic.log(
                    f"Snapshot cursor restore skipped for {file_path}: {type(e).__name__}: {e}",
                    "DEBUG",
                )
        try:
            scroll_value = int(state.get("scroll_value", 0))
            editor.verticalScrollBar().setValue(max(0, scroll_value))
        except Exception as e:
            self.console_logic.log(
                f"Snapshot scroll restore skipped for {file_path}: {type(e).__name__}: {e}",
                "DEBUG",
            )

        if self._pending_snapshot_active_path and self._pending_snapshot_active_path == file_path:
            idx = self.editor_manager.tab_widget.indexOf(editor)
            if idx >= 0:
                self.editor_manager.tab_widget.setCurrentIndex(idx)
                self._pending_snapshot_active_path = None

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
            self.config["last_session_state"] = self._collect_session_state()
            self.save_config()
            # --------------------------

            if self.find_dialog: self.find_dialog.close()
            if self.console_widget: self.console_widget.close()
            if hasattr(self, "console_logic"):
                self.console_logic.shutdown()
            if ENGINE_AVAILABLE and hasattr(lx_engine, "clear_logger"):
                try:
                    lx_engine.clear_logger()
                except Exception as e:
                    self.console_logic.log(
                        f"Engine logger cleanup skipped: {type(e).__name__}: {e}",
                        "DEBUG",
                    )
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
