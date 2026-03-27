import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QMimeData
from PyQt6.QtWidgets import QApplication, QWidget

from core.editor.editor_tab import EditorTab
from ui.main_window.main_window import MainWindow
from ui.dialogs.settings_dialog import SettingsDialog
from ui.menus.statusbar_menu import LxStatusBar


class _DummyConsole:
    def __init__(self):
        self.logs = []

    def log(self, message, level="INFO"):
        self.logs.append((message, level))


class _DummyLang:
    def __init__(self):
        self._data = {
            "label_line": "Ln",
            "label_column": "Col",
            "label_symbols": "Symbols",
            "status_health_normal": "HEALTH: Normal",
            "status_health_viewer": "HEALTH: Viewer",
            "status_health_guarded": "HEALTH: Guarded",
            "status_health_heavy": "HEALTH: Heavy",
            "status_size_label": "Size",
            "status_enc_conf_label": "EncConf",
        }

    def tr(self, key):
        return self._data.get(key, key)


class _DummyEditorManager:
    def __init__(self, editor):
        self._editor = editor

    def get_current_editor(self):
        return self._editor


class _DummyMainWindow(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.lang_handler = _DummyLang()
        self.editor_manager = _DummyEditorManager(editor)


class _FakeSignal:
    def __init__(self):
        self.connected = []
        self.disconnect_calls = 0

    def connect(self, callback):
        self.connected.append(callback)

    def disconnect(self):
        self.disconnect_calls += 1


class _FakeEditor:
    def __init__(self):
        self.cursorPositionChanged = _FakeSignal()
        self.textChanged = _FakeSignal()
        self.selectionChanged = _FakeSignal()


class _FakeStatusBar:
    def __init__(self):
        self.update_calls = 0

    def update_info(self):
        self.update_calls += 1


class _FakeTimer:
    def __init__(self):
        self.start_calls = 0
        self.stop_calls = 0

    def start(self):
        self.start_calls += 1

    def stop(self):
        self.stop_calls += 1


class TestSessionSafeStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_safe_edit_quick_revert_and_large_paste_guard(self):
        console = _DummyConsole()
        editor = EditorTab(console=console)
        original = "alpha\nbeta\n"
        editor.setPlainText(original)
        editor.enable_safe_edit_mode(snapshot_text=original)

        editor.setPlainText("changed")
        self.assertTrue(editor.quick_revert_safe_edit())
        self.assertEqual(editor.toPlainText(), original)

        mime = QMimeData()
        mime.setText("x" * 300_000)
        before = editor.toPlainText()
        editor.insertFromMimeData(mime)
        self.assertEqual(editor.toPlainText(), before)
        self.assertTrue(any("blocked huge paste" in msg for msg, _lvl in console.logs))

    def test_statusbar_insights_includes_health_size_and_confidence(self):
        editor = EditorTab(console=_DummyConsole())
        editor.setPlainText("hello world")
        editor.file_encoding = "utf-8"
        editor.file_encoding_confidence = 0.85
        editor.safe_edit_mode = True

        mw = _DummyMainWindow(editor)
        status = LxStatusBar(mw)
        status.set_display_mode("advanced")
        status.update_info()
        text = status.insights_label.text()

        self.assertIn("|", text)
        self.assertIn("B", text)
        self.assertIn("85%", text)

    def test_statusbar_dirty_file_size_cache_avoids_stat_and_tracks_buffer_length(self):
        editor = EditorTab(console=_DummyConsole())
        editor.file_path = "/tmp/lxnotes-dirty-cache.txt"
        editor.setPlainText("hello")
        editor.document().setModified(True)

        mw = _DummyMainWindow(editor)
        status = LxStatusBar(mw)
        status._insights_cache_ttl = 60.0

        with patch("ui.menus.statusbar_menu.os.stat", side_effect=AssertionError("stat() should not run for dirty buffers")):
            size1 = status._get_file_size(editor, editor.file_path, len(editor.toPlainText()))
            editor.setPlainText("hello world")
            editor.document().setModified(True)
            size2 = status._get_file_size(editor, editor.file_path, len(editor.toPlainText()))

        self.assertEqual(size1, 5)
        self.assertEqual(size2, 11)

    def test_statusbar_clean_file_size_cache_uses_mtime_and_skips_redundant_stats(self):
        editor = EditorTab(console=_DummyConsole())
        editor.file_path = "/tmp/lxnotes-clean-cache.txt"
        editor.setPlainText("hello")
        editor.document().setModified(False)

        mw = _DummyMainWindow(editor)
        status = LxStatusBar(mw)
        status._insights_cache_ttl = 60.0

        stat_calls = []

        def fake_stat(_path):
            stat_calls.append(_path)
            return SimpleNamespace(st_size=120, st_mtime_ns=1234)

        with patch("ui.menus.statusbar_menu.os.stat", side_effect=fake_stat):
            size1 = status._get_file_size(editor, editor.file_path, len(editor.toPlainText()))
            size2 = status._get_file_size(editor, editor.file_path, len(editor.toPlainText()))

        self.assertEqual(size1, 120)
        self.assertEqual(size2, 120)
        self.assertEqual(len(stat_calls), 1)

    def test_statusbar_clean_file_size_cache_refreshes_when_mtime_changes(self):
        editor = EditorTab(console=_DummyConsole())
        editor.file_path = "/tmp/lxnotes-mtime-cache.txt"
        editor.setPlainText("hello")
        editor.document().setModified(False)

        mw = _DummyMainWindow(editor)
        status = LxStatusBar(mw)
        status._insights_cache_ttl = 0.0

        stat_results = [
            SimpleNamespace(st_size=120, st_mtime_ns=111),
            SimpleNamespace(st_size=120, st_mtime_ns=111),
            SimpleNamespace(st_size=256, st_mtime_ns=222),
        ]
        calls = []

        def fake_stat(_path):
            calls.append(_path)
            return stat_results[len(calls) - 1]

        with patch("ui.menus.statusbar_menu.os.stat", side_effect=fake_stat):
            first = status._get_file_size(editor, editor.file_path, len(editor.toPlainText()))
            second = status._get_file_size(editor, editor.file_path, len(editor.toPlainText()))
            third = status._get_file_size(editor, editor.file_path, len(editor.toPlainText()))

        self.assertEqual(first, 120)
        self.assertEqual(second, 120)
        self.assertEqual(third, 256)
        self.assertEqual(len(calls), 3)

    def test_statusbar_simple_mode_hides_advanced_widgets(self):
        editor = EditorTab(console=_DummyConsole())
        editor.setPlainText("abc")
        mw = _DummyMainWindow(editor)
        status = LxStatusBar(mw)

        status.set_display_mode("simple")
        self.assertTrue(status.stats_label.isHidden())
        self.assertTrue(status.insights_label.isHidden())
        self.assertFalse(status.engine_label.isHidden())
        self.assertFalse(status.turbo_label.isHidden())
        self.assertFalse(status.encoding_label.isHidden())
        self.assertFalse(status.cursor_pos_label.isHidden())

        status.set_display_mode("advanced")
        self.assertFalse(status.stats_label.isHidden())
        self.assertFalse(status.insights_label.isHidden())

    def test_settings_apply_updates_statusbar_mode_immediately(self):
        fake_config = {"language": "en-us", "theme": "light", "status_bar_mode": "advanced", "last_session": []}
        with patch.object(MainWindow, "load_config", return_value=fake_config), patch.object(
            MainWindow, "save_config", lambda self: None
        ):
            window = MainWindow(startup_logs=[], platform_manager=None)
            dialog = SettingsDialog(window, theme_manager=window.theme_manager)
            self.assertTrue(dialog.advanced_statusbar_checkbox.isChecked())

            dialog.advanced_statusbar_checkbox.setChecked(False)
            dialog.apply_settings()

            self.assertEqual(window.config.get("status_bar_mode"), "simple")
            self.assertFalse(window.config.get("advanced_status_bar"))
            self.assertTrue(window.custom_status_bar.stats_label.isHidden())
            self.assertTrue(window.custom_status_bar.insights_label.isHidden())
            window.close()

    def test_on_tab_changed_updates_statusbar_immediately(self):
        fake = SimpleNamespace()
        fake.editor_manager = SimpleNamespace(get_current_editor=lambda: _FakeEditor())
        fake.edit_menu = SimpleNamespace(update_menu_states=lambda: None)
        fake.custom_status_bar = _FakeStatusBar()
        fake._statusbar_update_timer = _FakeTimer()
        fake.setup_context_menu_for_current = lambda: None
        fake._try_apply_pending_snapshot_state = lambda editor: None
        fake._schedule_statusbar_update = lambda: None
        fake._update_statusbar_now = lambda: fake.custom_status_bar.update_info()

        MainWindow.on_tab_changed(fake)

        self.assertEqual(fake.custom_status_bar.update_calls, 1)
        self.assertEqual(fake._statusbar_update_timer.start_calls, 0)

    def test_snapshot_collect_and_save_updates_config(self):
        fake_config = {"language": "en-us", "theme": "light", "status_bar_mode": "simple", "last_session": []}
        with patch.object(MainWindow, "load_config", return_value=fake_config), patch.object(
            MainWindow, "save_config", lambda self: None
        ):
            window = MainWindow(startup_logs=[], platform_manager=None)
            editor = window.editor_manager.get_current_editor()
            self.assertIsNotNone(editor)

            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
                tmp.write("snapshot content")
                tmp_path = tmp.name
            try:
                editor.file_path = tmp_path
                editor.setPlainText("snapshot content")
                cursor = editor.textCursor()
                cursor.setPosition(5)
                editor.setTextCursor(cursor)
                editor.document().setModified(False)

                state = window._collect_session_state()
                self.assertEqual(len(state.get("tabs", [])), 1)
                self.assertEqual(state["tabs"][0]["file_path"], tmp_path)
                self.assertEqual(state["tabs"][0]["cursor_position"], 5)

                window.save_session_snapshot()
                snapshots = window.config.get("session_snapshots", [])
                self.assertTrue(isinstance(snapshots, list) and snapshots)
                self.assertEqual(snapshots[-1]["tabs"][0]["file_path"], tmp_path)
            finally:
                window.close()
                os.unlink(tmp_path)

    def test_load_config_new_profile_defaults_to_simple_statusbar(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            holder = type("ConfigHolder", (), {})()
            holder.config_path = os.path.join(tmp_dir, "config.json")
            holder.legacy_config_path = os.path.join(tmp_dir, "legacy_config.json")
            config = MainWindow.load_config(holder)
            self.assertEqual(config.get("status_bar_mode"), "simple")


if __name__ == "__main__":
    unittest.main()
