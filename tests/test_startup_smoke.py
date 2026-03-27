import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.main_window.main_window import MainWindow


class TestStartupSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_main_window_can_be_constructed_offscreen(self):
        fake_config = {"language": "en-us", "theme": "light", "last_session": []}
        with patch.object(MainWindow, "load_config", return_value=fake_config):
            window = MainWindow(startup_logs=["[BOOT] smoke"], platform_manager=None)
            self.assertIsNotNone(window)
            self.assertIsNotNone(window.editor_manager)
            self.assertIsNotNone(window.file_handler)
            self.assertIsNotNone(window.custom_status_bar)
            window.close()


if __name__ == "__main__":
    unittest.main()
