import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication, QWidget, QTextEdit
from PyQt6.QtGui import QTextCursor

from ui.dialogs import find_replace_dialog
from ui.dialogs.find_replace_dialog import FindReplaceDialog


class _DummyLangHandler:
    def tr(self, key):
        return key


class _DummyConsoleLogic:
    def __init__(self):
        self.logs = []

    def log(self, message, level="INFO"):
        self.logs.append((message, level))


class _DummyMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.lang_handler = _DummyLangHandler()
        self.console_logic = _DummyConsoleLogic()


class _DummyEditorManager:
    def __init__(self, editor):
        self._editor = editor

    def get_current_editor(self):
        return self._editor


class TestFindReplaceCppPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _make_dialog(self, text):
        parent = _DummyMainWindow()
        editor = QTextEdit()
        editor.setPlainText(text)
        dialog = FindReplaceDialog(parent=parent, editor_manager=_DummyEditorManager(editor))
        return parent, editor, dialog

    def _select_text(self, editor, start, end):
        cursor = editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

    def test_find_next_uses_cpp_fast_path(self):
        parent, editor, dialog = self._make_dialog("abc def abc")
        dialog.find_input.setText("abc")
        dialog.case_cb.setChecked(True)
        dialog.words_cb.setChecked(True)
        editor.moveCursor(QTextCursor.MoveOperation.End)

        engine = Mock()
        engine.find_next_position.return_value = 0

        with patch.object(find_replace_dialog, "lx_engine", engine):
            dialog.find_next()

        engine.find_next_position.assert_called_once_with("abc def abc", "abc", True, True, 11, True)
        cursor = editor.textCursor()
        self.assertTrue(cursor.hasSelection())
        self.assertEqual(cursor.selectionStart(), 0)
        self.assertEqual(cursor.selectedText(), "abc")
        self.assertEqual(parent.console_logic.logs, [])

    def test_find_next_falls_back_when_cpp_unavailable(self):
        _, editor, dialog = self._make_dialog("abc def abc")
        dialog.find_input.setText("abc")
        editor.moveCursor(QTextCursor.MoveOperation.End)

        with patch.object(find_replace_dialog, "lx_engine", None):
            dialog.find_next()

        cursor = editor.textCursor()
        self.assertTrue(cursor.hasSelection())
        self.assertEqual(cursor.selectionStart(), 0)
        self.assertEqual(cursor.selectedText(), "abc")

    def test_find_next_skips_cpp_fast_path_for_huge_document(self):
        _, editor, dialog = self._make_dialog("abc def abc")
        dialog.find_input.setText("abc")
        editor.moveCursor(QTextCursor.MoveOperation.End)
        dialog._CPP_FIND_FASTPATH_MAX_CHARS = 3

        engine = Mock()
        engine.find_next_position.return_value = 0

        with patch.object(find_replace_dialog, "lx_engine", engine):
            dialog.find_next()

        engine.find_next_position.assert_not_called()
        cursor = editor.textCursor()
        self.assertTrue(cursor.hasSelection())
        self.assertEqual(cursor.selectionStart(), 0)

    def test_replace_all_uses_cpp_fast_path(self):
        parent, editor, dialog = self._make_dialog("foo Foo foo_bar foo")
        dialog.find_input.setText("foo")
        dialog.replace_input.setText("X")
        dialog.case_cb.setChecked(True)
        dialog.words_cb.setChecked(True)

        engine = Mock()
        engine.replace_all_with_options.return_value = "X Foo foo_bar X"

        with patch.object(find_replace_dialog, "lx_engine", engine):
            dialog.handle_replace_all()

        engine.replace_all_with_options.assert_called_once_with(
            "foo Foo foo_bar foo",
            "foo",
            "X",
            True,
            True,
        )
        self.assertEqual(editor.toPlainText(), "X Foo foo_bar X")
        self.assertEqual(parent.console_logic.logs[-1], ("Replace All completed (1 matches).", "SUCCESS"))

    def test_replace_all_falls_back_when_cpp_raises(self):
        parent, editor, dialog = self._make_dialog("one two one")
        dialog.find_input.setText("one")
        dialog.replace_input.setText("1")

        engine = SimpleNamespace(
            replace_all_with_options=Mock(side_effect=RuntimeError("boom"))
        )

        with patch.object(find_replace_dialog, "lx_engine", engine):
            dialog.handle_replace_all()

        self.assertEqual(editor.toPlainText(), "1 two 1")
        self.assertEqual(parent.console_logic.logs[-1], ("Replace All completed (2 matches).", "SUCCESS"))

    def test_replace_all_skips_precount_for_huge_doc_when_cpp_available(self):
        parent, editor, dialog = self._make_dialog("abc abc abc")
        dialog.find_input.setText("abc")
        dialog.replace_input.setText("x")
        dialog._CPP_REPLACE_COUNT_MAX_CHARS = 1
        dialog._count_matches = Mock(side_effect=AssertionError("pre-count should be skipped"))

        engine = Mock()
        engine.replace_all_with_options.return_value = "x x x"

        with patch.object(find_replace_dialog, "lx_engine", engine):
            dialog.handle_replace_all()

        self.assertEqual(editor.toPlainText(), "x x x")
        self.assertEqual(parent.console_logic.logs[-1], ("Replace All completed.", "SUCCESS"))


if __name__ == "__main__":
    unittest.main()
