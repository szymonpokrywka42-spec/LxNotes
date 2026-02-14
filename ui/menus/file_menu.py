from PyQt6.QtWidgets import QMenu, QFileDialog
from PyQt6.QtGui import QKeySequence, QAction
from PyQt6.QtCore import Qt
import os

class FileMenu(QMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.file_handler = main_window.file_handler
        self.console = main_window.console_logic

        # --- Definicja Akcji ---
        # Ustawiamy kontekst na WindowShortcut, żeby skróty działały "globalnie" w apce
        ctx = Qt.ShortcutContext.WindowShortcut

        self.open_action = QAction(self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open) # Ctrl+O
        self.open_action.setShortcutContext(ctx)
        self.open_action.triggered.connect(self.open_file)

        self.save_action = QAction(self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save) # Ctrl+S
        self.save_action.setShortcutContext(ctx)
        self.save_action.triggered.connect(self.save_file)

        self.save_as_action = QAction(self)
        self.save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.save_as_action.setShortcutContext(ctx)
        self.save_as_action.triggered.connect(self.save_file_as)

        self.print_action = QAction(self)
        self.print_action.setShortcut(QKeySequence.StandardKey.Print) # Ctrl+P
        self.print_action.setShortcutContext(ctx)
        self.print_action.triggered.connect(self.main_window.print_current)

        self.exit_action = QAction(self)
        self.exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        self.exit_action.setShortcutContext(ctx)
        self.exit_action.triggered.connect(self.exit_app)

        # --- Budowa Struktury Menu ---
        # Tutaj print jest tylko RAZ i nie ma duplikatów akcji z EditMenu
        self.addAction(self.open_action)
        self.addAction(self.save_action)
        self.addAction(self.save_as_action)
        self.addSeparator()
        self.addAction(self.print_action)
        self.addSeparator()
        self.addAction(self.exit_action)

        self.retranslate_ui()

    def retranslate_ui(self):
        """Dynamiczne tłumaczenie etykiet."""
        tr = self.main_window.lang_handler.tr
        self.setTitle(tr("menu_file"))
        
        self.open_action.setText(tr("action_open"))
        self.save_action.setText(tr("action_save"))
        self.save_as_action.setText(tr("action_save_as"))
        self.print_action.setText(tr("action_print"))
        self.exit_action.setText(tr("action_exit"))

    # --- Logika ---
    def open_file(self):
        tr = self.main_window.lang_handler.tr
        self.console.log("Opening file dialog...", "UI")
        
        path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            tr("dialog_open_title"),
            "",
            f"{tr('filter_text_files')} (*.txt);;{tr('filter_all_files')} (*)"
        )
        if path:
            self.file_handler.open_file(path)
            self.console.log(f"Loaded: {os.path.basename(path)}", "SUCCESS")

    def save_file(self):
        if self.main_window.editor_manager.get_current_editor():
            self.file_handler.save_file()
        else:
            self.console.log("Save failed: No active tab.", "WARN")

    def save_file_as(self):
        if self.main_window.editor_manager.get_current_editor():
            self.file_handler.save_file_as()

    def exit_app(self):
        self.console.log("Closing application...", "SYSTEM")
        self.main_window.close()