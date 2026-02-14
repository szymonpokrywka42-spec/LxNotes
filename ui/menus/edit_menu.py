from PyQt6.QtWidgets import QMenu, QDialog
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QFont
from PyQt6.QtCore import Qt
from ui.dialogs.font_settings_dialog import FontSettingsDialog
# Importujemy dialog, aby móc go wywołać
from ui.dialogs.goto_line_dialog import GotoLineDialog
import os

class EditMenu(QMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window

        # Ścieżka do ikon
        icon_path = os.path.join(os.path.dirname(__file__), "../../assets/icons/icon.png")
        self.font_icon = QIcon(icon_path)

        self._create_actions()
        self._build_menu()
        self.retranslate_ui()

    def _create_actions(self):
        # --- Zarządzanie kartami ---
        self.new_tab_action = QAction(self)
        self.new_tab_action.setShortcut(QKeySequence("Ctrl+N"))
        self.new_tab_action.triggered.connect(self.main_window.editor_manager.new_tab)

        self.close_tab_action = QAction(self)
        self.close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        self.close_tab_action.triggered.connect(self.close_current_tab)

        # --- Edycja standardowa ---
        self.undo_action = QAction(self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.undo)

        self.redo_action = QAction(self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self.redo)

        # --- Stylizacja ---
        self.bold_action = QAction(self)
        self.bold_action.setShortcut(QKeySequence.StandardKey.Bold)
        self.bold_action.setCheckable(True)
        self.bold_action.triggered.connect(lambda: self.toggle_style("bold"))

        self.italic_action = QAction(self)
        self.italic_action.setShortcut(QKeySequence.StandardKey.Italic)
        self.italic_action.setCheckable(True)
        self.italic_action.triggered.connect(lambda: self.toggle_style("italic"))

        self.underline_action = QAction(self)
        self.underline_action.setShortcut(QKeySequence.StandardKey.Underline)
        self.underline_action.setCheckable(True)
        self.underline_action.triggered.connect(lambda: self.toggle_style("underline"))

        # --- Pozostałe operacje ---
        self.cut_action = QAction(self)
        self.cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        self.cut_action.triggered.connect(self.cut)

        self.copy_action = QAction(self)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_action.triggered.connect(self.copy)

        self.paste_action = QAction(self)
        self.paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self.paste_action.triggered.connect(self.paste)
        
        # --- Szukanie i Nawigacja ---
        self.find_action = QAction(self)
        self.find_action.setShortcut(QKeySequence.StandardKey.Find)
        self.find_action.triggered.connect(self.main_window.show_find_replace)

        # NOWOŚĆ: Akcja skoku do linii
        self.goto_line_action = QAction(self)
        self.goto_line_action.setShortcut(QKeySequence("Ctrl+G"))
        self.goto_line_action.triggered.connect(self.open_goto_line)

        self.font_settings_action = QAction(self.font_icon, "", self)
        self.font_settings_action.triggered.connect(self.open_font_settings)

        self.select_all_action = QAction(self)
        self.select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.select_all_action.triggered.connect(self.select_all)

    def _build_menu(self):
        self.addAction(self.new_tab_action)
        self.addAction(self.close_tab_action)
        self.addSeparator()
        self.addAction(self.undo_action)
        self.addAction(self.redo_action)
        self.addSeparator()
        self.addAction(self.bold_action)
        self.addAction(self.italic_action)
        self.addAction(self.underline_action)
        self.addSeparator()
        self.addAction(self.cut_action)
        self.addAction(self.copy_action)
        self.addAction(self.paste_action)
        self.addSeparator()
        self.addAction(self.find_action)
        self.addAction(self.goto_line_action) # Dodano do menu
        self.addAction(self.font_settings_action)
        self.addSeparator()
        self.addAction(self.select_all_action)

    def retranslate_ui(self):
        tr = self.main_window.lang_handler.tr
        self.setTitle(tr("menu_edit"))
        
        translations = {
            self.new_tab_action: "action_new_tab",
            self.close_tab_action: "action_close_tab",
            self.undo_action: "action_undo",
            self.redo_action: "action_redo",
            self.bold_action: "font_bold",
            self.italic_action: "font_italic",
            self.underline_action: "font_underline",
            self.cut_action: "action_cut",
            self.copy_action: "action_copy",
            self.paste_action: "action_paste",
            self.find_action: "action_find_replace",
            self.goto_line_action: "action_goto_line", # Klucz tłumaczenia dla skoku
            self.font_settings_action: "action_font_settings",
            self.select_all_action: "action_select_all"
        }

        for action, key in translations.items():
            action.setText(tr(key))

    def open_goto_line(self):
        """Wywołuje dialog i przekazuje wynik do mostu w FileHandlerze."""
        dialog = GotoLineDialog(self.main_window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            line_number = dialog.get_line_number()
            # Wykorzystujemy FileHandler jako most do silnika C++
            self.main_window.file_handler.go_to_line(line_number)

    def toggle_style(self, style_type):
        editor = self.current_editor()
        if not editor: return

        if style_type == "bold":
            weight = QFont.Weight.Bold if self.bold_action.isChecked() else QFont.Weight.Normal
            editor.setFontWeight(weight.value)
        elif style_type == "italic":
            editor.setFontItalic(self.italic_action.isChecked())
        elif style_type == "underline":
            editor.setFontUnderline(self.underline_action.isChecked())

    def update_menu_states(self):
        editor = self.current_editor()
        if editor:
            self.bold_action.setChecked(editor.fontWeight() >= 600)
            self.italic_action.setChecked(editor.fontItalic())
            self.underline_action.setChecked(editor.fontUnderline())

    def current_editor(self):
        return self.main_window.editor_manager.get_current_editor()

    def close_current_tab(self):
        idx = self.main_window.editor_manager.tab_widget.currentIndex()
        if idx != -1: self.main_window.editor_manager.close_tab(idx)

    def open_font_settings(self):
        if editor := self.current_editor():
            dialog = FontSettingsDialog(editor, self.main_window)
            dialog.exec()

    def undo(self): 
        if e := self.current_editor(): e.undo()
    def redo(self): 
        if e := self.current_editor(): e.redo()
    def cut(self): 
        if e := self.current_editor(): e.cut()
    def copy(self): 
        if e := self.current_editor(): e.copy()
    def paste(self): 
        if e := self.current_editor(): e.paste()
    def select_all(self): 
        if e := self.current_editor(): e.selectAll()