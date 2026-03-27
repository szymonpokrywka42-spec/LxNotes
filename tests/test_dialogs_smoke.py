import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication, QWidget, QTextEdit
from PyQt6.QtGui import QTextCursor

from ui.dialogs.console import ConsoleDialog
from ui.dialogs.find_replace_dialog import FindReplaceDialog
from ui.dialogs.font_settings_dialog import FontSettingsDialog
from ui.dialogs.quick_open_dialog import QuickOpenDialog


class _DummyLangHandler:
    def tr(self, key):
        return key


class _DummyThemeManager:
    current_theme = "dark"


class _DummyConsoleLogic:
    def __init__(self):
        self.history = []
        self.command_history = []
        self.logs = []

    def execute_command(self, text):
        self.command_history.append(text)
        return None

    def log(self, message, level="INFO"):
        self.logs.append((message, level))


class _DummyMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.lang_handler = _DummyLangHandler()
        self.theme_manager = _DummyThemeManager()
        self.console_logic = _DummyConsoleLogic()


class _DummyEditorManager:
    def __init__(self, editor):
        self._editor = editor

    def get_current_editor(self):
        return self._editor


class TestDialogsSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _make_find_replace_dialog(self, text):
        parent = _DummyMainWindow()
        editor = QTextEdit()
        editor.setPlainText(text)
        em = _DummyEditorManager(editor)
        dialog = FindReplaceDialog(parent=parent, editor_manager=em)
        return parent, editor, dialog

    @staticmethod
    def _select_text(editor, start, end):
        cursor = editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

    def test_quick_open_filters_and_returns_selection(self):
        parent = _DummyMainWindow()
        dialog = QuickOpenDialog(parent=parent, files=["/tmp/a.txt", "/tmp/b.md"])
        dialog.search_input.setText("a.txt")
        selected = dialog.selected_path()
        self.assertTrue(selected.endswith("a.txt"))

    def test_font_dialog_safe_init_with_none_editor(self):
        parent = _DummyMainWindow()
        parent.console_logic = _DummyConsoleLogic()
        dialog = FontSettingsDialog(editor=None, parent=parent)
        dialog.apply()
        self.assertTrue(dialog is not None)

    def test_console_dialog_smoke(self):
        parent = _DummyMainWindow()
        logic = _DummyConsoleLogic()
        dialog = ConsoleDialog(parent=parent, logic=logic)
        dialog.input.setText("help")
        dialog.handle_input()
        self.assertEqual(logic.command_history[-1], "help")

    def test_find_replace_all_respects_case_sensitive(self):
        parent, editor, dialog = self._make_find_replace_dialog("foo Foo FOO foO")
        dialog.find_input.setText("foo")
        dialog.replace_input.setText("X")
        dialog.case_cb.setChecked(True)
        dialog.handle_replace_all()

        self.assertEqual(editor.toPlainText(), "X Foo FOO foO")

    def test_find_replace_all_respects_whole_words(self):
        parent, editor, dialog = self._make_find_replace_dialog("foo foo_bar barfoo foo foo.")
        dialog.find_input.setText("foo")
        dialog.replace_input.setText("X")
        dialog.words_cb.setChecked(True)
        dialog.handle_replace_all()

        self.assertEqual(editor.toPlainText(), "X foo_bar barfoo X X.")

    def test_find_next_wraps_to_document_start(self):
        parent, editor, dialog = self._make_find_replace_dialog("abc def abc")
        cursor = editor.textCursor()
        cursor.setPosition(len(editor.toPlainText()))
        editor.setTextCursor(cursor)
        dialog.find_input.setText("abc")
        dialog.find_next()

        found_cursor = editor.textCursor()
        self.assertTrue(found_cursor.hasSelection())
        self.assertEqual(found_cursor.selectionStart(), 0)
        self.assertEqual(found_cursor.selectedText(), "abc")

    def test_replace_replaces_only_current_match(self):
        parent, editor, dialog = self._make_find_replace_dialog("one two one")
        self._select_text(editor, 0, 3)
        dialog.find_input.setText("one")
        dialog.replace_input.setText("1")

        dialog.handle_replace()

        self.assertEqual(editor.toPlainText(), "1 two one")

    def test_replace_all_replaces_every_match(self):
        parent, editor, dialog = self._make_find_replace_dialog("one two one")
        dialog.find_input.setText("one")
        dialog.replace_input.setText("1")

        dialog.handle_replace_all()

        self.assertEqual(editor.toPlainText(), "1 two 1")


if __name__ == "__main__":
    unittest.main()
