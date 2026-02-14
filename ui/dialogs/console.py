from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QLineEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor

class ConsoleDialog(QDialog):
    def __init__(self, parent=None, logic=None):
        super().__init__(parent)
        self.logic = logic
        self.main_window = parent
        self.theme_manager = parent.theme_manager if parent else None
        self.history_index = -1
        
        self.resize(700, 450)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Usunięto setStyleSheet - teraz konsola pociągnie style z Twojego dark.qss / light.qss
        # W QSS używaj: QDialog#ConsoleDialog, QTextEdit#ConsoleDisplay, QLineEdit#ConsoleInput

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Wyświetlacz logów
        self.display = QTextEdit()
        self.display.setObjectName("ConsoleDisplay")
        self.display.setReadOnly(True)
        
        # Wybór fontu mono
        font = QFont("Cascadia Code", 10)
        if not font.fixedPitch(): font = QFont("Consolas", 10)
        self.display.setFont(font)
        layout.addWidget(self.display)

        # Input
        self.input = QLineEdit()
        self.input.setObjectName("ConsoleInput")
        self.input.setFont(font)
        self.input.installEventFilter(self)
        self.input.returnPressed.connect(self.handle_input)
        layout.addWidget(self.input)

        self.retranslate_ui()

        # Synchronizacja z historią logiki
        if self.logic:
            for msg in self.logic.history:
                self.append_text(msg)

    def get_color_for_level(self, level):
        """Zwraca kolor dopasowany do aktualnego motywu Evergreen."""
        is_dark = True
        if self.theme_manager:
            is_dark = self.theme_manager.current_theme == "dark"

        # Paleta Evergreen V2
        if is_dark:
            color_map = {
                "INFO": "#cccccc",     # Jasnoszary
                "SUCCESS": "#4ec9b0",  # Turkus
                "WARN": "#ce9178",     # Ceglany
                "ERROR": "#f44747",    # Czerwony
                "SYSTEM": "#569cd6",   # Błękit
                "BOOT": "#b5cea8",     # Jasna zieleń
                "ACTION": "#dcdcdc"
            }
        else:
            # Paleta dla jasnego motywu (bardziej nasycone kolory na białym tle)
            color_map = {
                "INFO": "#2d2d2d",     # Ciemny grafit
                "SUCCESS": "#058b72",  # Ciemny turkus
                "WARN": "#a31515",     # Ciemna czerwień
                "ERROR": "#cd3131",    # Wyrazisty czerwony
                "SYSTEM": "#005a9e",   # Ciemny niebieski
                "BOOT": "#228b22",     # Forest Green
                "ACTION": "#4f4f4f"
            }
        return color_map.get(level, color_map["INFO"])

    def append_text(self, text, level="INFO"):
        """Dodaje tekst z dynamicznym kolorowaniem HTML."""
        # Automatyczne wykrywanie poziomu z tagów w tekście [TAG]
        active_level = level
        for tag in ["INFO", "SUCCESS", "WARN", "ERROR", "SYSTEM", "BOOT", "ACTION"]:
            if f"[{tag}]" in text:
                active_level = tag
                break

        color = self.get_color_for_level(active_level)
        
        # Formatowanie HTML
        html_msg = f'<div style="color:{color}; white-space: pre-wrap;">{text}</div>'
        self.display.append(html_msg)
        
        # Auto-scroll
        self.display.moveCursor(QTextCursor.MoveOperation.End)

    def retranslate_ui(self):
        tr = self.main_window.lang_handler.tr
        self.setWindowTitle(tr("console_title"))
        self.input.setPlaceholderText(tr("console_placeholder"))

    def handle_input(self):
        text = self.input.text().strip()
        if not text: return
        
        self.history_index = -1
        result = self.logic.execute_command(text)
        
        if result == "clear":
            self.display.clear()
        elif result:
            system_prefix = self.main_window.lang_handler.tr("console_system_prefix")
            self.append_text(f"[{system_prefix}] {result}", "SYSTEM")
            
        self.input.clear()

    def eventFilter(self, source, event):
        if event.type() == event.Type.KeyPress and source is self.input:
            if event.key() == Qt.Key.Key_Up:
                self._browse_history(-1)
                return True
            elif event.key() == Qt.Key.Key_Down:
                self._browse_history(1)
                return True
        return super().eventFilter(source, event)

    def _browse_history(self, direction):
        if not self.logic or not self.logic.command_history: return
        self.history_index += direction
        self.history_index = max(-1, min(self.history_index, len(self.logic.command_history) - 1))
        
        if self.history_index == -1:
            self.input.clear()
        else:
            cmd = list(reversed(self.logic.command_history))[self.history_index]
            self.input.setText(cmd)