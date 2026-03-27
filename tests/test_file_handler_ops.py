import unittest
from unittest.mock import patch

from core.file import file_handler as fh


class DummySignal:
    def __init__(self):
        self._subs = []

    def connect(self, cb):
        self._subs.append(cb)

    def emit(self, *args, **kwargs):
        for cb in list(self._subs):
            cb(*args, **kwargs)


class DummyProgress:
    def __init__(self):
        self.canceled = DummySignal()

    def setValue(self, _value):
        pass

    def close(self, *args, **kwargs):
        _ = args, kwargs
        pass


class DummyTimer:
    def __init__(self):
        self.timeout = DummySignal()

    def start(self, _ms):
        pass


class DummyFileDialog:
    next_exec_result = True
    next_selected_files = []

    class AcceptMode:
        AcceptSave = 1

    class FileMode:
        AnyFile = 1

    class Option:
        DontConfirmOverwrite = 1

    def __init__(self, *args, **kwargs):
        _ = args, kwargs
        self._selected = list(self.next_selected_files)

    def setAcceptMode(self, _value):
        pass

    def setFileMode(self, _value):
        pass

    def setNameFilters(self, _value):
        pass

    def setDefaultSuffix(self, _value):
        pass

    def setOption(self, _option, _enabled):
        pass

    def selectFile(self, path):
        self._selected = [path]

    def exec(self):
        return bool(self.next_exec_result)

    def selectedFiles(self):
        return list(self._selected)


class DummyRecentFiles:
    def __init__(self, *args, **kwargs):
        self.files = []

    def add_file(self, path):
        self.files.append(path)


class DummyConsole:
    def __init__(self):
        self.logs = []

    def log(self, msg, level="INFO"):
        self.logs.append((msg, level))


class DummyStatusBar:
    def showMessage(self, _msg, _timeout=None):
        pass


class DummyCustomStatusBar:
    def __init__(self):
        self.updated = 0

    def update_info(self):
        self.updated += 1


class DummyDocument:
    def __init__(self):
        self._modified = False

    def setModified(self, value):
        self._modified = bool(value)

    def isModified(self):
        return self._modified


class DummyCursor:
    def __init__(self):
        self.position = None

    def setPosition(self, value):
        self.position = value


class DummyBlock:
    def __init__(self, position=None, valid=True):
        self._position = position
        self._valid = valid

    def isValid(self):
        return self._valid

    def position(self):
        return self._position


class DummyLineDocument:
    def __init__(self, line_offsets):
        self._line_offsets = list(line_offsets)
        self.calls = []

    def findBlockByLineNumber(self, line_number):
        self.calls.append(line_number)
        if 0 <= line_number < len(self._line_offsets):
            return DummyBlock(self._line_offsets[line_number], True)
        return DummyBlock(valid=False)


class DummyEditor:
    def __init__(self, document=None):
        self.file_path = None
        self.file_encoding = "utf-8"
        self.file_encoding_confidence = 0.0
        self.large_file_mode = False
        self._text = ""
        self._full_text = ""
        self._doc = DummyDocument()
        self._document = document
        self._cursor = DummyCursor()
        self.cursor_set_to = None
        self.cursor_visible_called = False

    def setPlainText(self, text):
        self._text = text
        self._full_text = text

    def toPlainText(self):
        return self._text

    def get_full_text(self):
        return self._full_text if self.large_file_mode else self._text

    def document(self):
        return self._document if self._document is not None else self._doc

    def textCursor(self):
        return self._cursor

    def setTextCursor(self, cursor):
        self.cursor_set_to = cursor.position

    def ensureCursorVisible(self):
        self.cursor_visible_called = True


class DummyEditorManager:
    def __init__(self):
        self.tab_widget = DummyTabWidget()
        self._last_editor = None

    def new_tab(self, title="Untitled"):
        _ = title
        self._last_editor = DummyEditor()
        self.tab_widget.addTab(self._last_editor, title)
        return self._last_editor

    def handle_text_changed(self, _editor):
        pass

    def get_current_editor(self):
        current = self.tab_widget.currentWidget()
        return current if current is not None else self._last_editor


class DummyTabWidget:
    def __init__(self):
        self._tabs = []
        self._titles = []
        self._current_index = -1

    def addTab(self, widget, _title):
        self._tabs.append(widget)
        self._titles.append(_title)
        if self._current_index == -1:
            self._current_index = 0
        return len(self._tabs) - 1

    def count(self):
        return len(self._tabs)

    def widget(self, index):
        if 0 <= index < len(self._tabs):
            return self._tabs[index]
        return None

    def currentIndex(self):
        return self._current_index

    def setCurrentIndex(self, index):
        if 0 <= index < len(self._tabs):
            self._current_index = index

    def currentWidget(self):
        return self.widget(self._current_index)

    def indexOf(self, widget):
        try:
            return self._tabs.index(widget)
        except ValueError:
            return -1

    def setTabText(self, index, title):
        if 0 <= index < len(self._titles):
            self._titles[index] = title

    def tabText(self, index):
        if 0 <= index < len(self._titles):
            return self._titles[index]
        return ""


class DummyMainWindow:
    def __init__(self):
        self.console_logic = DummyConsole()
        self.editor_manager = DummyEditorManager()
        self.custom_status_bar = DummyCustomStatusBar()
        self._status_bar = DummyStatusBar()
        self.config = {"save_encoding_policy": "preserve"}

    def statusBar(self):
        return self._status_bar


class DummyWorker:
    auto_finish = True
    last_instance = None

    def __init__(self, task_type, path, content=None):
        self.task_type = task_type
        self.path = path
        self.content = content
        self.used_encoding = "utf-8"
        self.save_encoding = "utf-8"
        self.progress = DummySignal()
        self.log_signal = DummySignal()
        self.finished = DummySignal()
        self.error = DummySignal()
        DummyWorker.last_instance = self

    def start(self):
        if not self.auto_finish:
            return
        if self.task_type == "open":
            self.finished.emit("data")
        else:
            self.used_encoding = self.save_encoding
            self.finished.emit(self.path)

    def requestInterruption(self):
        pass


class TestFileHandlerOps(unittest.TestCase):
    def test_open_logs_start_success(self):
        main_window = DummyMainWindow()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: DummyProgress()
        ):
            handler = fh.FileHandler(main_window)
            handler.open_file(path="example.txt")

        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any(m.startswith("OPEN START") for m in messages))
        self.assertTrue(any(m.startswith("OPEN SUCCESS") for m in messages))

    def test_duplicate_save_blocked(self):
        main_window = DummyMainWindow()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: DummyProgress()
        ):
            handler = fh.FileHandler(main_window)
            editor = DummyEditor()
            DummyWorker.auto_finish = False
            try:
                first = handler._async_save("a.txt", "content", editor)
                second = handler._async_save("a.txt", "content", editor)
            finally:
                DummyWorker.auto_finish = True
                worker_id, _worker = handler._find_active_worker("save", "a.txt")
                if worker_id:
                    handler._cleanup_worker(worker_id)

        self.assertTrue(first)
        self.assertFalse(second)
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("SAVE SKIPPED" in m for m in messages))

    def test_cancel_logs_and_cleans_worker(self):
        main_window = DummyMainWindow()
        progress = DummyProgress()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: progress
        ):
            handler = fh.FileHandler(main_window)
            DummyWorker.auto_finish = False
            try:
                handler.open_file(path="cancel.txt")
                progress.canceled.emit()
                worker_id, _worker = handler._find_active_worker("open", "cancel.txt")
            finally:
                DummyWorker.auto_finish = True
                if worker_id:
                    handler._cleanup_worker(worker_id)

        self.assertIsNone(worker_id)
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("Open CANCELED" in m for m in messages))

    def test_cancel_ignores_late_finished_signal(self):
        main_window = DummyMainWindow()
        progress = DummyProgress()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: progress
        ):
            handler = fh.FileHandler(main_window)
            DummyWorker.auto_finish = False
            try:
                handler.open_file(path="late.txt")
                progress.canceled.emit()
                self.assertIsNotNone(DummyWorker.last_instance)
                DummyWorker.last_instance.finished.emit("late-data")
            finally:
                DummyWorker.auto_finish = True
                worker_id, _worker = handler._find_active_worker("open", "late.txt")
                if worker_id:
                    handler._cleanup_worker(worker_id)

        self.assertIsNone(main_window.editor_manager.get_current_editor())
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertFalse(any("OPEN SUCCESS: late.txt" in m for m in messages))

    def test_open_file_by_path_error_cleans_worker(self):
        main_window = DummyMainWindow()
        worker_id = None
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch("os.path.exists", return_value=True), patch.object(
            fh.QMessageBox, "critical", return_value=None
        ):
            handler = fh.FileHandler(main_window)
            DummyWorker.auto_finish = False
            try:
                started = handler.open_file_by_path("restore-error.txt")
                self.assertTrue(started)
                self.assertIsNotNone(DummyWorker.last_instance)
                DummyWorker.last_instance.error.emit("boom")
                worker_id, _worker = handler._find_active_worker("open", "restore-error.txt")
            finally:
                DummyWorker.auto_finish = True
                if worker_id:
                    handler._cleanup_worker(worker_id)

        self.assertIsNone(worker_id)
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("Operation failed: boom" in m for m in messages))

    def test_save_cancel_ignores_late_error_signal(self):
        main_window = DummyMainWindow()
        progress = DummyProgress()
        worker_id = None
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: progress
        ):
            handler = fh.FileHandler(main_window)
            editor = DummyEditor()
            DummyWorker.auto_finish = False
            try:
                started = handler._async_save("late-save.txt", "content", editor)
                self.assertTrue(started)
                progress.canceled.emit()
                self.assertIsNotNone(DummyWorker.last_instance)
                DummyWorker.last_instance.error.emit("late-error")
                worker_id, _worker = handler._find_active_worker("save", "late-save.txt")
            finally:
                DummyWorker.auto_finish = True
                if worker_id:
                    handler._cleanup_worker(worker_id)

        self.assertIsNone(worker_id)
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("Save CANCELED: by user" in m for m in messages))
        self.assertFalse(any("Operation failed: late-error" in m for m in messages))

    def test_save_cancel_ignores_late_finished_signal(self):
        main_window = DummyMainWindow()
        progress = DummyProgress()
        worker_id = None
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: progress
        ):
            handler = fh.FileHandler(main_window)
            editor = DummyEditor()
            DummyWorker.auto_finish = False
            try:
                started = handler._async_save("late-save-ok.txt", "content", editor)
                self.assertTrue(started)
                progress.canceled.emit()
                self.assertIsNotNone(DummyWorker.last_instance)
                DummyWorker.last_instance.finished.emit("late-save-ok.txt")
                worker_id, _worker = handler._find_active_worker("save", "late-save-ok.txt")
            finally:
                DummyWorker.auto_finish = True
                if worker_id:
                    handler._cleanup_worker(worker_id)

        self.assertIsNone(worker_id)
        self.assertFalse(editor.document().isModified())
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("Save CANCELED: by user" in m for m in messages))
        self.assertFalse(any("SAVE SUCCESS: late-save-ok.txt" in m for m in messages))

    def test_save_as_returns_false_when_dialog_canceled(self):
        main_window = DummyMainWindow()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "QTimer", DummyTimer
        ), patch.object(fh, "QFileDialog", DummyFileDialog):
            handler = fh.FileHandler(main_window)
            editor = DummyEditor()
            main_window.editor_manager._last_editor = editor
            DummyFileDialog.next_exec_result = False
            DummyFileDialog.next_selected_files = []
            with patch.object(handler, "_async_save", return_value=True) as save_mock:
                result = handler.save_file_as()

        self.assertFalse(result)
        save_mock.assert_not_called()

    def test_save_success_updates_default_metadata(self):
        main_window = DummyMainWindow()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: DummyProgress()
        ):
            handler = fh.FileHandler(main_window)
            editor = DummyEditor()
            started = handler._async_save("meta.txt", "content", editor)

        self.assertTrue(started)
        self.assertEqual(editor.file_encoding, "utf-8")
        self.assertEqual(editor.file_encoding_confidence, 1.0)
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("Saved using encoding policy" in m for m in messages))

    def test_save_uses_editor_encoding_when_available(self):
        main_window = DummyMainWindow()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: DummyProgress()
        ):
            handler = fh.FileHandler(main_window)
            editor = DummyEditor()
            editor.file_encoding = "cp1250"
            started = handler._async_save(
                "meta-cp1250.txt",
                "content",
                editor,
                save_encoding=handler._resolve_save_encoding(editor),
            )

        self.assertTrue(started)
        self.assertEqual(editor.file_encoding, "cp1250")
        self.assertEqual(editor.file_encoding_confidence, 1.0)

    def test_save_policy_utf8_overrides_editor_encoding(self):
        main_window = DummyMainWindow()
        main_window.config["save_encoding_policy"] = "utf-8"
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: DummyProgress()
        ):
            handler = fh.FileHandler(main_window)
            editor = DummyEditor()
            editor.file_path = "force-utf8.txt"
            editor.file_encoding = "cp1250"
            main_window.editor_manager._last_editor = editor
            started = handler.save_file()

        self.assertTrue(started)
        self.assertEqual(editor.file_encoding, "utf-8")
        self.assertEqual(editor.file_encoding_confidence, 1.0)

    def test_save_as_existing_file_no_does_not_save(self):
        main_window = DummyMainWindow()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "QTimer", DummyTimer
        ), patch.object(fh, "QFileDialog", DummyFileDialog):
            handler = fh.FileHandler(main_window)
            editor = DummyEditor()
            main_window.editor_manager._last_editor = editor
            DummyFileDialog.next_exec_result = True
            DummyFileDialog.next_selected_files = ["/tmp/existing.txt"]
            with patch("os.path.exists", return_value=True), patch.object(
                fh.QMessageBox, "question", return_value=fh.QMessageBox.StandardButton.No
            ), patch.object(handler, "_async_save", return_value=True) as save_mock:
                result = handler.save_file_as()

        self.assertFalse(result)
        save_mock.assert_not_called()
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("Save As canceled for existing file" in m for m in messages))

    def test_save_as_existing_file_yes_calls_async_save(self):
        main_window = DummyMainWindow()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "QTimer", DummyTimer
        ), patch.object(fh, "QFileDialog", DummyFileDialog):
            handler = fh.FileHandler(main_window)
            editor = DummyEditor()
            editor._text = "payload"
            main_window.editor_manager._last_editor = editor
            DummyFileDialog.next_exec_result = True
            DummyFileDialog.next_selected_files = ["/tmp/existing.txt"]
            with patch("os.path.exists", return_value=True), patch.object(
                fh.QMessageBox, "question", return_value=fh.QMessageBox.StandardButton.Yes
            ), patch.object(handler, "_async_save", return_value=True) as save_mock:
                result = handler.save_file_as()

        self.assertTrue(result)
        save_mock.assert_called_once()
        args = save_mock.call_args[0]
        self.assertEqual(args[0], "/tmp/existing.txt")
        self.assertEqual(args[1], "payload")
        self.assertIs(args[2], editor)

    def test_save_all_handles_modified_file_backed_and_untitled_tabs(self):
        main_window = DummyMainWindow()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh, "QFileDialog", DummyFileDialog
        ), patch.object(fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: DummyProgress()), patch(
            "os.path.exists", return_value=False
        ):
            handler = fh.FileHandler(main_window)
            file_editor = DummyEditor()
            file_editor.file_path = "backed.txt"
            file_editor.setPlainText("backed payload")
            file_editor.document().setModified(True)

            untitled_editor = DummyEditor()
            untitled_editor.setPlainText("untitled payload")
            untitled_editor.document().setModified(True)

            main_window.editor_manager.tab_widget._tabs = [file_editor, untitled_editor]
            main_window.editor_manager.tab_widget._current_index = 1
            main_window.editor_manager._last_editor = untitled_editor

            DummyFileDialog.next_exec_result = True
            DummyFileDialog.next_selected_files = ["/tmp/saved-from-save-all.txt"]
            saved = handler.save_all()

        self.assertTrue(saved)
        self.assertFalse(file_editor.document().isModified())
        self.assertFalse(untitled_editor.document().isModified())
        self.assertEqual(untitled_editor.file_path, "/tmp/saved-from-save-all.txt")
        self.assertEqual(main_window.editor_manager.tab_widget.currentIndex(), 1)
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any(msg.startswith("SAVE ALL START") for msg in messages))
        self.assertTrue(any("SAVE SUCCESS: backed.txt" in msg for msg in messages))
        self.assertTrue(any("SAVE SUCCESS: /tmp/saved-from-save-all.txt" in msg for msg in messages))

    def test_save_all_uses_full_text_for_large_viewer_tabs(self):
        main_window = DummyMainWindow()
        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "FileWorker", DummyWorker
        ), patch.object(fh, "QTimer", DummyTimer), patch.object(
            fh.FileHandler, "_show_progress", lambda *_args, **_kwargs: DummyProgress()
        ), patch("os.path.exists", return_value=False):
            handler = fh.FileHandler(main_window)
            editor = DummyEditor()
            editor.file_path = "large.txt"
            editor.large_file_mode = True
            editor._text = "visible chunk only"
            editor._full_text = "full large payload"
            editor.document().setModified(True)
            main_window.editor_manager.tab_widget._tabs = [editor]
            main_window.editor_manager._last_editor = editor

            saved = handler.save_all()

        self.assertTrue(saved)
        self.assertIsNotNone(DummyWorker.last_instance)
        self.assertEqual(DummyWorker.last_instance.content, "full large payload")
        self.assertFalse(editor.document().isModified())
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("SAVE ALL START" in msg for msg in messages))

    def test_go_to_line_uses_qt_document_without_plain_text_copy(self):
        main_window = DummyMainWindow()
        document = DummyLineDocument([0, 8, 18])
        editor = DummyEditor(document=document)
        editor.toPlainText = lambda: self.fail("go_to_line should not copy the whole text when Qt lookup is available")
        main_window.editor_manager._last_editor = editor

        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "QTimer", DummyTimer
        ), patch.object(fh, "ENGINE_AVAILABLE", True), patch.object(fh, "lx_engine", None):
            handler = fh.FileHandler(main_window)
            handler.go_to_line(2)

        self.assertEqual(document.calls, [1])
        self.assertEqual(editor.cursor_set_to, 8)
        self.assertTrue(editor.cursor_visible_called)
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("Jumped to line 2" in m for m in messages))

    def test_go_to_line_falls_back_to_engine_offset(self):
        main_window = DummyMainWindow()
        editor = DummyEditor()
        editor._text = "one\ntwo\nthree"
        editor._doc = DummyDocument()
        main_window.editor_manager._last_editor = editor

        class DummyEngine:
            def __init__(self):
                self.calls = []

            def get_line_offset(self, content, line_num):
                self.calls.append((content, line_num))
                return 4

        engine = DummyEngine()

        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "QTimer", DummyTimer
        ), patch.object(fh, "ENGINE_AVAILABLE", True), patch.object(fh, "lx_engine", engine):
            handler = fh.FileHandler(main_window)
            handler.go_to_line(2)

        self.assertEqual(engine.calls, [("one\ntwo\nthree", 2)])
        self.assertEqual(editor.cursor_set_to, 4)
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("Jumped to line 2" in m for m in messages))

    def test_go_to_line_logs_out_of_range_without_plain_text_copy(self):
        main_window = DummyMainWindow()
        document = DummyLineDocument([0, 5])
        editor = DummyEditor(document=document)
        editor.toPlainText = lambda: self.fail("go_to_line should not copy the whole text on out-of-range Qt lookup")
        main_window.editor_manager._last_editor = editor

        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "QTimer", DummyTimer
        ), patch.object(fh, "ENGINE_AVAILABLE", True), patch.object(fh, "lx_engine", object()):
            handler = fh.FileHandler(main_window)
            handler.go_to_line(5)

        self.assertEqual(document.calls, [4])
        self.assertIsNone(editor.cursor_set_to)
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("is out of range" in m for m in messages))

    def test_go_to_line_large_viewer_uses_editor_jump_api(self):
        main_window = DummyMainWindow()
        editor = DummyEditor()
        editor.large_file_mode = True
        calls = {"line": None}

        def jump_to_large_line(line_num):
            calls["line"] = line_num
            return True

        editor.jump_to_large_line = jump_to_large_line
        main_window.editor_manager._last_editor = editor

        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "QTimer", DummyTimer
        ):
            handler = fh.FileHandler(main_window)
            handler.go_to_line(321)

        self.assertEqual(calls["line"], 321)
        messages = [msg for msg, _level in main_window.console_logic.logs]
        self.assertTrue(any("Large Viewer Mode" in m for m in messages))

    def test_quick_revert_safe_edit_without_status_bar_does_not_crash(self):
        main_window = DummyMainWindow()
        main_window.custom_status_bar = None
        editor = DummyEditor()
        editor.quick_revert_safe_edit = lambda: True
        main_window.editor_manager._last_editor = editor

        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "QTimer", DummyTimer
        ):
            handler = fh.FileHandler(main_window)
            result = handler.quick_revert_safe_edit()

        self.assertTrue(result)

    def test_quick_revert_safe_edit_updates_status_bar_when_available(self):
        main_window = DummyMainWindow()
        editor = DummyEditor()
        editor.quick_revert_safe_edit = lambda: True
        main_window.editor_manager._last_editor = editor

        with patch.object(fh, "RecentFiles", DummyRecentFiles), patch.object(
            fh, "QTimer", DummyTimer
        ):
            handler = fh.FileHandler(main_window)
            result = handler.quick_revert_safe_edit()

        self.assertTrue(result)
        self.assertEqual(main_window.custom_status_bar.updated, 1)


if __name__ == "__main__":
    unittest.main()
