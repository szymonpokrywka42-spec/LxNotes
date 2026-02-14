from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFileDialog, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt
import os

class OpenDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent 
        self.selected_path = None
        self.setFixedWidth(450)

        # Evergreen Styling - ciemniejsza paleta i lepsze przyciski
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #d4d4d4; }
            QLabel { font-weight: bold; color: #cccccc; }
            QPushButton { 
                padding: 10px; border-radius: 4px; border: 1px solid #444; 
                background-color: #333; color: white;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton#primaryButton { 
                background-color: #0e639c; border: none; font-weight: bold; 
            }
            QPushButton#primaryButton:hover { background-color: #1177bb; }
            QPushButton#primaryButton:disabled { background-color: #252526; color: #555; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Nagłówek i ikona (symulowana tekstem)
        header_layout = QHBoxLayout()
        self.label = QLabel()
        self.label.setStyleSheet("font-size: 14px;")
        header_layout.addWidget(self.label)
        layout.addLayout(header_layout)

        # Kontener na wybór pliku
        self.file_frame = QFrame()
        self.file_frame.setStyleSheet("background-color: #252526; border-radius: 4px; border: 1px solid #333;")
        frame_layout = QVBoxLayout(self.file_frame)

        self.browse_button = QPushButton()
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_button.clicked.connect(self.browse_file)
        frame_layout.addWidget(self.browse_button)

        self.path_display = QLabel()
        self.path_display.setStyleSheet("font-weight: normal; color: #888; font-size: 11px; border: none;")
        self.path_display.setWordWrap(True)
        self.path_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.path_display)
        
        layout.addWidget(self.file_frame)

        # Przyciski dolne
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton()
        self.cancel_btn.clicked.connect(self.reject)
        
        self.ok_button = QPushButton()
        self.ok_button.setObjectName("primaryButton")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_button)
        layout.addLayout(btn_layout)

        self.retranslate_ui()

    def retranslate_ui(self):
        """Dynamiczne tłumaczenie interfejsu."""
        tr = self.main_window.lang_handler.tr
        
        self.setWindowTitle(tr("open_title"))
        self.label.setText(tr("open_header"))
        
        if not self.selected_path:
            self.browse_button.setText(tr("open_btn_select"))
            self.path_display.setText(tr("open_no_file"))
        else:
            self.browse_button.setText(tr("open_btn_change"))
            filename = os.path.basename(self.selected_path)
            self.path_display.setText(f"{tr('open_selected')}:\n{filename}")

        self.cancel_btn.setText(tr("btn_cancel"))
        self.ok_button.setText(tr("open_btn_confirm"))

    def browse_file(self):
        tr = self.main_window.lang_handler.tr
        
        # Rozszerzone filtry dla większej uniwersalności
        filters = f"{tr('filter_text')} (*.txt);;Markdown (*.md);;Code (*.cpp *.h *.py);;{tr('filter_all')} (*)"
        
        path, _ = QFileDialog.getOpenFileName(
            self, 
            tr("open_dialog_window_title"), 
            "", 
            filters
        )
        
        if path:
            self.selected_path = path
            self.ok_button.setEnabled(True)
            self.main_window.console_logic.log(f"File staged for opening: {os.path.basename(path)}", "INFO")
            self.retranslate_ui()

    def get_path(self):
        return self.selected_path