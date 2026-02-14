from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QTextCharFormat, QFont, QColor, QTextOption

class EditorTab(QTextEdit):
    def __init__(self, console=None):
        super().__init__()
        self.console = console  # Referencja do console_logic
        self.is_turbo_mode = False  # Flaga dla silnika C++ / High Performance
        
        # Konfiguracja bazowa
        self.setAcceptRichText(True)
        self.setUndoRedoEnabled(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        
        # Evergreen UI: Ustawienie szerokości tabulatora na 4 spacje
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        
        tab_stop = 4
        metrics = self.fontMetrics()
        self.setTabStopDistance(tab_stop * metrics.horizontalAdvance(' '))

        if self.console:
            self.console.log("EditorTab: Evergreen core initialized.", "DEBUG")

    def set_turbo_mode(self, enabled: bool):
        """Przełącza edytor w tryb maksymalnej wydajności (Raw Text)."""
        self.is_turbo_mode = enabled
        
        if enabled:
            # Tryb Turbo: Optymalizacja pod kątem szybkości renderowania
            self.setAcceptRichText(False)
            self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
            
            # Wymuszamy czytelny font monospace dla trybu surowego
            turbo_font = QFont("Courier New", 10)
            self.setFont(turbo_font)
            
            if self.console:
                self.console.log("TURBO MODE ACTIVE: RichText/Wrap disabled. Engine acceleration ready.", "ENGINE")
        else:
            # Powrót do standardu
            self.setAcceptRichText(True)
            self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            if self.console:
                self.console.log("Turbo Mode disabled. Standard features restored.", "INFO")

    # --- FORMATOWANIE (Blokowane w Turbo Mode) ---

    def set_font(self, family: str, size: int):
        if self._check_turbo("font change"): return
        fmt = QTextCharFormat()
        fmt.setFontFamily(family)
        fmt.setFontPointSize(size)
        self.merge_format_on_selection(fmt)

    def set_bold(self, enable: bool):
        if self._check_turbo("bold formatting"): return
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if enable else QFont.Weight.Normal)
        self.merge_format_on_selection(fmt)

    def set_italic(self, enable: bool):
        if self._check_turbo("italic formatting"): return
        fmt = QTextCharFormat()
        fmt.setFontItalic(enable)
        self.merge_format_on_selection(fmt)

    def set_underline(self, enable: bool):
        if self._check_turbo("underline formatting"): return
        fmt = QTextCharFormat()
        fmt.setFontUnderline(enable)
        self.merge_format_on_selection(fmt)

    def set_text_color(self, color: QColor):
        if self._check_turbo("color change"): return
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        self.merge_format_on_selection(fmt)

    # --- LOGIKA POMOCNICZA ---

    def merge_format_on_selection(self, fmt: QTextCharFormat):
        """Aplikuje formatowanie do zaznaczenia lub słowa pod kursorem."""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            # Jeśli nic nie zaznaczono, formatuj słowo pod kursorem
            cursor.select(cursor.SelectionType.WordUnderCursor)
        
        cursor.mergeCharFormat(fmt)
        self.mergeCurrentCharFormat(fmt)

    def _check_turbo(self, action: str) -> bool:
        """Zwraca True jeśli akcja jest zablokowana przez Turbo Mode."""
        if self.is_turbo_mode:
            if self.console:
                self.console.log(f"Blocked: '{action}' is disabled in Turbo Mode.", "WARN")
            return True
        return False