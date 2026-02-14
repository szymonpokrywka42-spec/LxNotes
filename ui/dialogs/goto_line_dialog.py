from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel
from PyQt6.QtGui import QIntValidator
from PyQt6.QtCore import Qt

class GotoLineDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.tr = parent.lang_handler.tr  # Pobieramy tłumaczenia
        
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(self.tr("menu_goto_line") or "Go To Line")
        self.setFixedWidth(300)
        
        # Usuwamy znak zapytania z paska tytułu (standard w nowoczesnych apkach)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)

        # Etykieta
        self.label = QLabel(self.tr("label_enter_line") or "Enter line number:")
        layout.addWidget(self.label)

        # Pole wpisywania (tylko liczby)
        self.line_input = QLineEdit()
        self.line_input.setValidator(QIntValidator(1, 9999999)) # Walidator, żeby nie wpisać liter
        self.line_input.setPlaceholderText("1")
        layout.addWidget(self.line_input)

        # Przyciski
        btn_layout = QHBoxLayout()
        self.btn_go = QPushButton(self.tr("btn_go") or "Go")
        self.btn_go.setDefault(True) # Reaguje na Enter
        self.btn_go.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton(self.tr("btn_cancel") or "Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_go)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def get_line_number(self):
        """Zwraca wpisaną liczbę."""
        text = self.line_input.text()
        return int(text) if text else 1