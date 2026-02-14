from PyQt6.QtWidgets import QMenu, QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QPixmap, QAction
from PyQt6.QtCore import Qt
import os
import sys

class InfoMenu(QMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window

        self.about_action = QAction(self)
        self.about_action.triggered.connect(self.show_about)
        self.addAction(self.about_action)
        
        self.retranslate_ui()

    def retranslate_ui(self):
        tr = self.main_window.lang_handler.tr
        self.setTitle(tr("menu_info"))
        self.about_action.setText(tr("action_about"))

    def show_about(self):
        """Wyświetla okno About z obsługą ścieżek bezwzględnych."""
        tr = self.main_window.lang_handler.tr
        
        # --- USTALANIE ŚCIEŻKI BAZOWEJ (Pancerne rozwiązanie) ---
        # Pozwala znaleźć ikony i zasoby niezależnie od sposobu uruchomienia
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            # Lokalizacja pliku info_menu.py
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            # Zakładając strukturę: src/menus/info_menu.py -> wychodzimy do głównego folderu
            base_dir = os.path.abspath(os.path.join(current_file_dir, "../../"))

        dialog = QDialog(self.main_window)
        dialog.setWindowTitle(tr("about_title"))
        dialog.setFixedSize(360, 420)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # --- LOGO (Ścieżka bezwzględna) ---
        icon_path = os.path.join(base_dir, "assets", "icons", "about_lxico.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label = QLabel()
                icon_label.setPixmap(pixmap.scaled(90, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(icon_label)

        # --- POBIERANIE DANYCH ---
        description = tr("about_description")
        v_label = tr("about_version")
        c_label = tr("about_created_by")
        
        # Pobieramy źródło ikon
        icons_info = tr("icons_source")
        
        # Fallback, jeśli plik językowy nie został załadowany poprawnie przez błąd ścieżek
        if icons_info == "icons_source" or not icons_info:
            icons_info = "Źródło ikon: https://icons8.com/"

        is_dark = getattr(self.main_window.theme_manager, "current_theme", "dark") == "dark"
        accent_color = "#569cd6" if is_dark else "#005a9e"
        secondary_text = "#888888" if is_dark else "#555555"
        border_color = "#444444" if is_dark else "#dddddd"

        # --- KONSTRUKCJA UI (HTML) ---
        about_html = (
            f"<div style='text-align: center;'>"
            f"  <span style='font-size: 22px; font-weight: bold;'>LxNotes</span><br>"
            f"  <span style='color: {secondary_text};'>{description}</span>"
            f"  <br><br>"
            f"  <div style='font-size: 13px;'>"
            f"    {v_label}: <b style='color: {accent_color};'>1.5 Stable</b><br>"
            f"    {c_label}: <b>Szymon Pokrywka</b>"
            f"  </div>"
            f"  <br>"
            f"  <hr style='border: 0; border-top: 1px solid {border_color};'>"
            f"  <div style='margin-top: 10px; font-size: 10px; color: {secondary_text};'>"
            f"    {icons_info}"
            f"  </div>"
            f"</div>"
        )

        text_label = QLabel(about_html)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setWordWrap(True)
        text_label.setOpenExternalLinks(True) 
        layout.addWidget(text_label)

        layout.addStretch()

        close_btn = QPushButton(tr("btn_close"))
        close_btn.setObjectName("primaryButton")
        close_btn.setMinimumHeight(35)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setObjectName("AboutDialog") 
        dialog.exec()
