import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication, QWidget, QDialog

from ui.dialogs.quick_open_dialog import MAX_RENDERED_RESULTS, QuickOpenDialog


class _DummyLangHandler:
    def tr(self, key):
        return key


class _DummyParent(QWidget):
    def __init__(self):
        super().__init__()
        self.lang_handler = _DummyLangHandler()


class TestQuickOpenDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _make_dialog(self, files):
        parent = _DummyParent()
        dialog = QuickOpenDialog(parent=parent, files=files)
        return parent, dialog

    def test_ranks_prefix_name_before_contained_name_before_path(self):
        parent, dialog = self._make_dialog(
            [
                "/tmp/project/docs/readme.txt",
                "/tmp/project/src/hello_readme.txt",
                "/tmp/project/readme_notes/guide.txt",
                "/tmp/project/src/readme.txt",
            ]
        )

        dialog.search_input.setText("read")

        self.assertEqual(
            dialog._filtered_files,
            [
                "/tmp/project/docs/readme.txt",
                "/tmp/project/src/readme.txt",
                "/tmp/project/src/hello_readme.txt",
                "/tmp/project/readme_notes/guide.txt",
            ],
        )

    def test_filters_out_non_matching_files(self):
        parent, dialog = self._make_dialog(
            [
                "/tmp/project/src/app.py",
                "/tmp/project/src/notes.txt",
                "/tmp/project/docs/readme.md",
            ]
        )

        dialog.search_input.setText("app")

        self.assertEqual(dialog._filtered_files, ["/tmp/project/src/app.py"])

    def test_limits_rendered_results_to_top_300(self):
        files = [f"/tmp/project/file_{i:04d}.txt" for i in range(MAX_RENDERED_RESULTS + 75)]
        parent, dialog = self._make_dialog(files)

        dialog.search_input.setText("")

        self.assertEqual(dialog.file_list.count(), MAX_RENDERED_RESULTS)
        self.assertEqual(dialog._filtered_files[0], "/tmp/project/file_0000.txt")
        self.assertEqual(dialog._filtered_files[-1], f"/tmp/project/file_{MAX_RENDERED_RESULTS - 1:04d}.txt")

    def test_enter_accepts_selected_item(self):
        parent, dialog = self._make_dialog(["/tmp/project/a.txt", "/tmp/project/b.txt"])
        dialog.search_input.setText("b")

        dialog._accept_selected()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.selected_path(), "/tmp/project/b.txt")


if __name__ == "__main__":
    unittest.main()
