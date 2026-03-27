import unittest

from core.editor.console_logic import ConsoleLogic


class _DummyRecentFiles:
    def __init__(self, files=None):
        self._files = list(files or [])

    def get_files(self):
        return list(self._files)


class _DummyFileHandler:
    def __init__(self, recent_files=None, save_all_result=True):
        self.recent_files = _DummyRecentFiles(recent_files)
        self.save_all_result = save_all_result
        self.opened = []
        self.save_all_calls = 0

    def open_file(self, path):
        self.opened.append(path)
        return True

    def save_all_workflow(self):
        self.save_all_calls += 1
        return self.save_all_result


class _DummyDocument:
    def __init__(self, modified=True):
        self._modified = modified

    def isModified(self):
        return self._modified


class _DummyEditor:
    def __init__(self, modified=True):
        self._document = _DummyDocument(modified=modified)

    def document(self):
        return self._document


class _DummyEditorManager:
    def __init__(self, editors=None):
        self._editors = list(editors or [])
        self.saved_editors = None

    def get_all_editors(self):
        return list(self._editors)

    def save_all_sequence(self, editors):
        self.saved_editors = list(editors)
        return True


class _DummyMainWindow:
    def __init__(self, file_handler=None, editor_manager=None):
        self.console_widget = None
        self.console_dialog = None
        self.file_handler = file_handler
        self.editor_manager = editor_manager
        self.closed = False

    def close(self):
        self.closed = True


class _DummyMainWindowWithRecent(_DummyMainWindow):
    def __init__(self, recent_files=None, save_all_result=True, editor_manager=None):
        super().__init__(
            file_handler=_DummyFileHandler(
                recent_files=recent_files,
                save_all_result=save_all_result,
            ),
            editor_manager=editor_manager,
        )


class TestConsoleHelp(unittest.TestCase):
    def setUp(self):
        self.logic = ConsoleLogic(_DummyMainWindow())

    def tearDown(self):
        self.logic.shutdown()

    def test_help_overview_contains_all_documented_commands(self):
        text = self.logic.execute_command("help")
        for name, doc in self.logic.COMMAND_DOCS.items():
            self.assertIn(doc["usage"], text, msg=f"Missing usage for command '{name}'")

    def test_help_command_details_for_open(self):
        text = self.logic.execute_command("help open")
        self.assertIn("Command: open", text)
        self.assertIn("Usage: open <path>", text)
        self.assertIn("Examples:", text)

    def test_help_supports_alias_details(self):
        text = self.logic.execute_command("help sys-info")
        self.assertIn("Command: sys", text)
        self.assertIn("Aliases: sys-info", text)

    def test_help_includes_new_commands(self):
        text = self.logic.execute_command("help")
        self.assertIn("save-all", text)
        self.assertIn("recent", text)
        self.assertIn("open-recent", text)

    def test_recent_lists_numbered_files(self):
        logic = ConsoleLogic(
            _DummyMainWindowWithRecent(
                recent_files=["/tmp/alpha.md", "/tmp/beta.md"],
            )
        )
        self.addCleanup(logic.shutdown)

        text = logic.execute_command("recent")
        self.assertIn("Recent files:", text)
        self.assertIn("1. /tmp/alpha.md", text)
        self.assertIn("2. /tmp/beta.md", text)

    def test_open_recent_opens_selected_file(self):
        main_window = _DummyMainWindowWithRecent(
            recent_files=["/tmp/alpha.md", "/tmp/beta.md"],
        )
        logic = ConsoleLogic(main_window)
        self.addCleanup(logic.shutdown)

        text = logic.execute_command("open-recent 2")
        self.assertEqual(main_window.file_handler.opened, ["/tmp/beta.md"])
        self.assertIn("Opening recent file: /tmp/beta.md", text)

    def test_open_recent_out_of_range_returns_clear_message(self):
        main_window = _DummyMainWindowWithRecent(
            recent_files=["/tmp/alpha.md", "/tmp/beta.md"],
        )
        logic = ConsoleLogic(main_window)
        self.addCleanup(logic.shutdown)

        text = logic.execute_command("open-recent 9")
        self.assertIn("out of range", text)
        self.assertEqual(main_window.file_handler.opened, [])

    def test_save_all_uses_available_workflow(self):
        main_window = _DummyMainWindowWithRecent(
            recent_files=["/tmp/alpha.md"],
            save_all_result=True,
        )
        logic = ConsoleLogic(main_window)
        self.addCleanup(logic.shutdown)

        text = logic.execute_command("save-all")
        self.assertEqual(main_window.file_handler.save_all_calls, 1)
        self.assertIn("Save All completed.", text)

    def test_save_all_falls_back_to_editor_manager_sequence(self):
        editors = [_DummyEditor(modified=True), _DummyEditor(modified=False)]
        editor_manager = _DummyEditorManager(editors=editors)
        main_window = _DummyMainWindowWithRecent(
            recent_files=["/tmp/alpha.md"],
            editor_manager=editor_manager,
        )
        main_window.file_handler.save_all_workflow = None
        logic = ConsoleLogic(main_window)
        self.addCleanup(logic.shutdown)

        text = logic.execute_command("save-all")
        self.assertEqual(editor_manager.saved_editors, [editors[0]])
        self.assertIn("Save All completed.", text)


if __name__ == "__main__":
    unittest.main()
