import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox


MAX_RENDERED_RESULTS = 300


class QuickOpenDialog(QDialog):
    def __init__(self, parent=None, files=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Open")
        self.setModal(True)
        self.resize(760, 420)

        self._files = [f for f in (files or []) if isinstance(f, str)]
        self._filtered_files = []

        layout = QVBoxLayout(self)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Type file name or path...")
        self.search_input.textChanged.connect(self._refresh_list)
        self.search_input.returnPressed.connect(self._accept_selected)
        layout.addWidget(self.search_input)

        self.file_list = QListWidget(self)
        self.file_list.itemDoubleClicked.connect(self._accept_selected)
        layout.addWidget(self.file_list)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.accepted.connect(self._accept_selected)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._refresh_list()
        self.retranslate_ui()

    def retranslate_ui(self):
        tr = None
        if self.parent() and hasattr(self.parent(), "lang_handler"):
            tr = self.parent().lang_handler.tr

        if tr:
            title = tr("quick_open_title")
            if title != "quick_open_title":
                self.setWindowTitle(title)
            placeholder = tr("quick_open_placeholder")
            if placeholder != "quick_open_placeholder":
                self.search_input.setPlaceholderText(placeholder)

    @staticmethod
    def _normalize_query(text):
        return (text or "").strip().casefold()

    @staticmethod
    def _match_score(path, query):
        if not query:
            return 0

        name = os.path.basename(path)
        name_folded = name.casefold()
        path_folded = path.casefold()

        if name_folded.startswith(query):
            return 0
        if query in name_folded:
            return 1
        if query in path_folded:
            return 2
        return None

    def _refresh_list(self, *_args):
        query = self._normalize_query(self.search_input.text())
        self.file_list.clear()

        ranked_files = []
        for index, path in enumerate(self._files):
            score = self._match_score(path, query)
            if score is not None:
                ranked_files.append((score, index, path))

        ranked_files.sort(key=lambda entry: (entry[0], entry[1]))
        self._filtered_files = [path for _, _, path in ranked_files[:MAX_RENDERED_RESULTS]]

        for path in self._filtered_files:
            name = os.path.basename(path)
            item = QListWidgetItem(f"{name}\n{path}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.file_list.addItem(item)

        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)

    def _accept_selected(self, *_args):
        if self.file_list.currentItem():
            self.accept()

    def selected_path(self):
        item = self.file_list.currentItem()
        if not item:
            return ""
        return item.data(Qt.ItemDataRole.UserRole) or ""
