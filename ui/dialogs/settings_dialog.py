from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QComboBox, QHBoxLayout, QFrame, QStyledItemDelegate, QStyleOptionComboBox, QStyle)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPalette, QPainter, QPen, QColor, QPolygonF


class ArrowComboBox(QComboBox):
    """ComboBox z ręcznie rysowanym chevronem, niezależnym od stylu platformy."""
    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Celowo jawny kolor: unikamy problemów, gdy paleta Qt nie odzwierciedla QSS.
        theme_mode = self.property("themeMode") or "dark"
        arrow_color = QColor("#DAF1DE") if theme_mode == "dark" else QColor("#163832")
        if not self.isEnabled():
            arrow_color.setAlpha(120)

        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        arrow_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )

        cx = float(arrow_rect.center().x())
        cy = float(arrow_rect.center().y())
        triangle = QPolygonF(
            [
                QPointF(cx - 4.0, cy - 1.5),
                QPointF(cx + 4.0, cy - 1.5),
                QPointF(cx, cy + 3.0),
            ]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(arrow_color)
        painter.drawPolygon(triangle)

class SettingsDialog(QDialog):
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.main_window = parent 
        self.theme_manager = theme_manager
        self.setFixedWidth(400)
        
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # --- SEKCJA: WYGLĄD ---
        self.label_appearance = QLabel()
        self.label_appearance.setObjectName("sectionHeader")
        layout.addWidget(self.label_appearance)

        theme_layout = QHBoxLayout()
        self.label_theme_mode = QLabel()
        theme_layout.addWidget(self.label_theme_mode)
        
        self.theme_selector = ArrowComboBox()
        self.theme_selector.setItemDelegate(QStyledItemDelegate()) 
        
        # DODANO: Opcja systemowa dla motywu
        # Używamy findData/currentData, więc przechowujemy klucze "light", "dark", "system"
        self.theme_selector.addItem("Light", "light")
        self.theme_selector.addItem("Dark", "dark")
        self.theme_selector.addItem("System", "system")
        
        # Ustawienie aktualnego wyboru z konfiguracji
        current_theme_cfg = self.main_window.config.get("theme", "system")
        idx_theme = self.theme_selector.findData(current_theme_cfg)
        self.theme_selector.setCurrentIndex(idx_theme if idx_theme >= 0 else 2)
            
        theme_layout.addWidget(self.theme_selector)
        layout.addLayout(theme_layout)

        self.line = QFrame()
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setObjectName("settingsSeparator")
        layout.addWidget(self.line)

        # --- SEKCJA: JĘZYK ---
        self.label_language = QLabel()
        self.label_language.setObjectName("sectionHeader")
        layout.addWidget(self.label_language)

        lang_layout = QHBoxLayout()
        self.label_select_lang = QLabel()
        lang_layout.addWidget(self.label_select_lang)
        
        self.lang_selector = ArrowComboBox()
        self.lang_selector.setItemDelegate(QStyledItemDelegate())
        
        # DODANO: Opcja systemowa na początku listy
        self.lang_selector.addItem("System", "system")
        
        languages = [
            ("Deutsch", "de-de"),
            ("English", "en-us"),
            ("Español", "es-es"),
            ("Français", "fr-fr"),
            ("Italiano", "it-it"),
            ("Polski", "pl-pl"),
            ("Português", "pt-br"),
            ("Svenska", "sv"),
            ("Tiếng Việt", "vi"),
            ("العربية", "ar"),  # Arabski
            ("Русский", "ru-ru"),  # Rosyjski
            ("Українська", "uk-ua"),  # Ukraiński
            ("日本語", "ja-jp"),  # Japoński
            ("简体中文 (Jiǎntǐ Zhōngwén)", "zh-cn"),  # Chiński
            ("한국어", "ko")  # Koreański
        ]

        for text, code in languages:
            self.lang_selector.addItem(text, code)
        
        # Ustawienie aktualnego wyboru języka
        current_lang_cfg = self.main_window.config.get("language", "system")
        index = self.lang_selector.findData(current_lang_cfg)
        if index >= 0:
            self.lang_selector.setCurrentIndex(index)
        
        lang_layout.addWidget(self.lang_selector)
        layout.addLayout(lang_layout)

        layout.addStretch()

        # --- PRZYCISKI AKCJI ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.cancel_button = QPushButton()
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setObjectName("secondaryButton")
        
        self.apply_button = QPushButton()
        self.apply_button.setObjectName("primaryButton") 
        self.apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_button.clicked.connect(self.apply_settings)
        
        btn_layout.addWidget(self.cancel_button)
        btn_layout.addWidget(self.apply_button)
        layout.addLayout(btn_layout)

        self._update_combo_arrow_theme()
        self.retranslate_ui()

    def _update_combo_arrow_theme(self):
        current_theme = getattr(self.theme_manager, "current_theme", None)
        if current_theme not in ("dark", "light"):
            current_theme = "dark" if QPalette().color(QPalette.ColorRole.Window).lightness() < 128 else "light"

        self.theme_selector.setProperty("themeMode", current_theme)
        self.lang_selector.setProperty("themeMode", current_theme)
        self.theme_selector.update()
        self.lang_selector.update()

    def retranslate_ui(self):
        tr = self.main_window.lang_handler.tr
        self.setWindowTitle(tr("settings_title"))
        self.label_appearance.setText(tr("settings_appearance"))
        self.label_theme_mode.setText(tr("settings_theme_mode"))
        self.label_language.setText(tr("settings_language"))
        self.label_select_lang.setText(tr("settings_select_lang"))
        self.cancel_button.setText(tr("btn_cancel"))
        self.apply_button.setText(tr("settings_btn_apply"))
        
        # Aktualizacja tekstu "System" w ComboBoxach na przetłumaczony
        sys_text = tr("settings_system")
        self.theme_selector.setItemText(self.theme_selector.findData("system"), sys_text)
        self.lang_selector.setItemText(self.lang_selector.findData("system"), sys_text)

    def apply_settings(self):
        # 1. Pobranie wyborów
        selected_theme = self.theme_selector.currentData() # "light", "dark" lub "system"
        selected_lang = self.lang_selector.currentData()   # "pl-pl", "en-us" lub "system"

        # 2. Zapis do configu (ważne, aby MainWindow pamiętał to po restarcie)
        self.main_window.config["theme"] = selected_theme
        self.main_window.config["language"] = selected_lang
        self.main_window.save_config() # Zakładam, że masz taką metodę

        # 3. Aplikacja motywu
        if selected_theme == "system":
            is_dark = QPalette().color(QPalette.ColorRole.Window).lightness() < 128
            theme_to_apply = "dark" if is_dark else "light"
        else:
            theme_to_apply = selected_theme
        
        if self.theme_manager:
            self.theme_manager.apply_theme(theme_to_apply)
            self._update_combo_arrow_theme()

        # 4. Aplikacja języka
        lang_to_load = selected_lang
        if selected_lang == "system":
            lang_to_load = self.main_window.lang_handler.get_system_language()

        if self.main_window.lang_handler.load_language(lang_to_load):
            self.main_window.refresh_ui_texts()
            self.retranslate_ui()
            
            msg = f"{self.main_window.lang_handler.tr('console_lang_changed')}: {lang_to_load.upper()}"
            self.main_window.console_logic.log(msg, "SUCCESS")

        self.accept()
