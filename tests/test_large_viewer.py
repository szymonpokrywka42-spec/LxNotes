import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent

from core.editor import editor_tab as et
from core.file import file_handler as fh


class _DummyConsole:
    def __init__(self):
        self.logs = []

    def log(self, message, level="INFO"):
        self.logs.append((message, level))


class _DummyTimer:
    def __init__(self):
        class _Signal:
            def connect(self, _cb):
                pass

        self.timeout = _Signal()

    def start(self, _ms):
        pass


class _DummyRecentFiles:
    def __init__(self, *args, **kwargs):
        self.items = []

    def add_file(self, path):
        self.items.append(path)


class _DummyEditorManager:
    def __init__(self, editor):
        self._editor = editor
        self.handled = 0

    def get_current_editor(self):
        return self._editor

    def handle_text_changed(self, _editor):
        self.handled += 1


class _DummyMainWindow:
    def __init__(self, editor):
        self.console_logic = _DummyConsole()
        self.editor_manager = _DummyEditorManager(editor)


class TestLargeViewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_enable_large_viewer_python_fallback_state_and_label(self):
        editor = et.EditorTab(console=_DummyConsole())
        content = "a" * 230000
        with patch.object(et, "_ENGINE_AVAILABLE", False):
            editor.enable_large_file_mode(content, chunk_size=100000)

        self.assertTrue(editor.large_file_mode)
        self.assertTrue(editor.isReadOnly())
        self.assertEqual(editor.get_virtual_char_count(), len(content))
        self.assertEqual(editor._large_chunk_count, 3)
        self.assertTrue(editor.get_large_viewer_label().startswith("VIEW 1/3"))
        self.assertEqual(editor.get_full_text(), content)

    def test_large_viewer_chunk_switch_loads_expected_slice(self):
        editor = et.EditorTab(console=_DummyConsole())
        content = ("0123456789" * 25000)  # 250000 chars
        with patch.object(et, "_ENGINE_AVAILABLE", False):
            editor.enable_large_file_mode(content, chunk_size=100000)
            editor._load_large_chunk(1)

        expected = content[100000:200000]
        self.assertEqual(editor.toPlainText(), expected)
        self.assertEqual(editor._large_chunk_index, 1)
        self.assertEqual(editor.get_large_viewer_label(), "VIEW 2/3 RO")

    def test_load_current_full_editable_disables_large_mode_and_keeps_text(self):
        editor = et.EditorTab(console=_DummyConsole())
        content = "x" * 60000
        with patch.object(et, "_ENGINE_AVAILABLE", False):
            editor.enable_large_file_mode(content, chunk_size=100000)

        main_window = _DummyMainWindow(editor)
        with patch.object(fh, "RecentFiles", _DummyRecentFiles), patch.object(
            fh, "QTimer", _DummyTimer
        ), patch.object(fh, "ENGINE_AVAILABLE", True):
            handler = fh.FileHandler(main_window)
            result = handler.load_current_full_editable()

        self.assertTrue(result)
        self.assertFalse(editor.large_file_mode)
        self.assertFalse(editor.isReadOnly())
        self.assertEqual(editor.toPlainText(), content)
        self.assertTrue(editor.is_turbo_mode)
        self.assertEqual(main_window.editor_manager.handled, 1)

    def test_large_viewer_keypress_blocks_edit_and_logs_hint_once(self):
        console = _DummyConsole()
        editor = et.EditorTab(console=console)
        content = "sample\n" * 20000
        with patch.object(et, "_ENGINE_AVAILABLE", False):
            editor.enable_large_file_mode(content, chunk_size=100000)

        before = editor.toPlainText()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "a")
        editor.keyPressEvent(event)
        editor.keyPressEvent(event)
        after = editor.toPlainText()

        self.assertEqual(before, after)
        self.assertTrue(editor._large_ro_hint_shown)
        hint_logs = [m for m, lvl in console.logs if "Large Viewer Mode is read-only" in m and lvl == "INFO"]
        self.assertEqual(len(hint_logs), 1)

    def test_large_viewer_chunk_cache_reuses_loaded_chunk(self):
        editor = et.EditorTab(console=_DummyConsole())
        content = "x" * 300000
        with patch.object(et, "_ENGINE_AVAILABLE", False):
            editor.enable_large_file_mode(content, chunk_size=100000)

        fetch_calls = {"count": 0}
        original_fetch = editor._fetch_large_chunk_text

        def counted_fetch(idx):
            fetch_calls["count"] += 1
            return original_fetch(idx)

        editor._large_chunk_cache = {}
        editor._large_chunk_cache_order = []
        editor._fetch_large_chunk_text = counted_fetch

        editor._load_large_chunk(1)
        first_count = fetch_calls["count"]
        editor._load_large_chunk(1)

        self.assertGreaterEqual(first_count, 1)
        self.assertEqual(fetch_calls["count"], first_count)

    def test_large_viewer_recommended_chunk_size_grows_with_file(self):
        self.assertLess(
            et.EditorTab._recommend_chunk_size(9_000_000),
            et.EditorTab._recommend_chunk_size(50_000_000),
        )
        self.assertLess(
            et.EditorTab._recommend_chunk_size(50_000_000),
            et.EditorTab._recommend_chunk_size(120_000_000),
        )

    def test_large_viewer_cache_respects_char_budget(self):
        editor = et.EditorTab(console=_DummyConsole())
        content = "0123456789" * 50000  # 500k chars
        with patch.object(et, "_ENGINE_AVAILABLE", False):
            editor.enable_large_file_mode(content, chunk_size=100000)
        editor._large_chunk_cache_char_budget = 150000
        editor._large_chunk_cache_limit = 10
        editor._large_chunk_cache = {}
        editor._large_chunk_cache_order = []
        editor._large_chunk_cache_chars = 0

        for idx in [0, 1, 2, 3]:
            editor._load_large_chunk(idx)

        self.assertLessEqual(editor._large_chunk_cache_chars, editor._large_chunk_cache_char_budget)

    def test_large_viewer_jump_to_line_fallback(self):
        editor = et.EditorTab(console=_DummyConsole())
        lines = [f"line {i}" for i in range(1, 5001)]
        content = "\n".join(lines)
        with patch.object(et, "_ENGINE_AVAILABLE", False):
            editor.enable_large_file_mode(content, chunk_size=6000)

        ok = editor.jump_to_large_line(1200)
        self.assertTrue(ok)
        self.assertTrue(editor.large_file_mode)
        self.assertEqual(editor.textCursor().blockNumber() + 1, 1200)

    def test_large_viewer_next_previous_chunk_navigation(self):
        editor = et.EditorTab(console=_DummyConsole())
        content = "x" * 260000
        with patch.object(et, "_ENGINE_AVAILABLE", False):
            editor.enable_large_file_mode(content, chunk_size=100000)

        self.assertEqual(editor._large_chunk_index, 0)
        self.assertTrue(editor.next_large_chunk())
        self.assertEqual(editor._large_chunk_index, 1)
        self.assertTrue(editor.next_large_chunk())
        self.assertEqual(editor._large_chunk_index, 2)
        self.assertFalse(editor.next_large_chunk())
        self.assertTrue(editor.previous_large_chunk())
        self.assertEqual(editor._large_chunk_index, 1)


if __name__ == "__main__":
    unittest.main()
