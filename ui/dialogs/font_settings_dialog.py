from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QFontComboBox, QSpinBox,
    QPushButton, QColorDialog, QWidget
)
from PyQt6.QtGui import QColor, QFont, QTextCharFormat
from PyQt6.QtCore import Qt

class FontSettingsDialog(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.main_window = parent 
        
        # --- BEZPIECZNE DANE INICJALNE ---
        # Nie pytamy o format, dopóki nie musimy, używamy właściwości edytora
        self.init_family = editor.font().family()
        self.init_size = int(editor.fontPointSize()) if editor.fontPointSize() > 0 else editor.font().pointSize()
        self.selected_color = editor.textColor() if hasattr(editor, 'textColor') else QColor("#ffffff")

        self.setup_ui()
        self.retranslate_ui()

    def setup_ui(self):
        self.setMinimumWidth(350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # --- WYBÓR CZCIONKI ---
        self.label_family = QLabel()
        layout.addWidget(self.label_family)
        
        self.font_box = QFontComboBox()
        # Ustawiamy czcionkę na tę, która jest aktualnie w edytorze
        self.font_box.setCurrentFont(QFont(self.init_family))
        layout.addWidget(self.font_box)

        # --- ROZMIAR ---
        self.label_size = QLabel()
        layout.addWidget(self.label_size)
        
        self.size_box = QSpinBox()
        self.size_box.setRange(6, 150)
        self.size_box.setValue(self.init_size if self.init_size > 0 else 12)
        layout.addWidget(self.size_box)

        # --- KOLOR ---
        self.color_btn = QPushButton()
        self.color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color_btn.clicked.connect(self.pick_color)
        self._update_color_preview()
        layout.addWidget(self.color_btn)

        layout.addStretch()

        # --- PRZYCISKI AKCJI ---
        btn_layout = QHBoxLayout()
        self.close_btn = QPushButton()
        self.close_btn.clicked.connect(self.reject)
        
        self.apply_btn = QPushButton()
        self.apply_btn.setObjectName("primaryButton") # Jeśli używasz QSS
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self.apply)
        
        btn_layout.addWidget(self.close_btn)
        btn_layout.addWidget(self.apply_btn)
        layout.addLayout(btn_layout)

    def _update_color_preview(self):
        # Prosty styl dla przycisku koloru
        color_hex = self.selected_color.name()
        self.color_btn.setStyleSheet(f"background-color: {color_hex}; color: {'black' if self.selected_color.lightness() > 128 else 'white'}; border: 1px solid #555; padding: 5px;")

    def retranslate_ui(self):
        def get_tr(key, default):
            try:
                t = self.main_window.lang_handler.tr(key)
                return t if t != key else default
            except:
                return default

        self.setWindowTitle(get_tr("font_title", "Font Settings"))
        self.label_family.setText(get_tr("font_label_family", "Font Family"))
        self.label_size.setText(get_tr("font_label_size", "Size"))
        self.color_btn.setText(get_tr("font_btn_color", "Pick Color"))
        self.apply_btn.setText(get_tr("btn_apply", "Apply"))
        self.close_btn.setText(get_tr("btn_cancel", "Cancel"))

    def pick_color(self):
        color = QColorDialog.getColor(self.selected_color, self, "Pick Font Color")
        if color.isValid():
            self.selected_color = color
            self._update_color_preview()

    def apply(self):
        if not self.editor:
            self.reject()
            return

        # Pobieramy obecny format, żeby NIE nadpisać Bold/Italic ustawionego w menu
        fmt = self.editor.currentCharFormat()
        
        # Zmieniamy tylko to, co jest w tym oknie
        fmt.setFontFamily(self.font_box.currentFont().family())
        fmt.setFontPointSize(float(self.size_box.value()))
        fmt.setForeground(self.selected_color)

        # Aplikujemy bezpiecznie
        self.editor.setCurrentCharFormat(fmt)
        
        if hasattr(self.main_window, 'console_logic'):
            self.main_window.console_logic.log(f"Font updated: {fmt.fontFamily()} {fmt.fontPointSize()}pt", "INFO")
                
        self.accept()