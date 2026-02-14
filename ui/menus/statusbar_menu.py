from PyQt6.QtWidgets import QStatusBar, QLabel

class LxStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("lxStatusBar")
        self.main_window = parent 
        
        # 1. Status Silnika (Engine)
        self.engine_label = QLabel(" Engine: Py ")
        self.engine_label.setObjectName("engineStatusLabel")
        
        # 2. Status Turbo Mode (NOWOŚĆ)
        self.turbo_label = QLabel("") 
        self.turbo_label.setObjectName("turboStatusLabel")
        
        # 3. Statystyki symboli
        self.stats_label = QLabel(" Symbols: 0 ")
        self.stats_label.setMinimumWidth(120)
        
        # 4. Pozycja kursora (Ln, Col)
        self.cursor_pos_label = QLabel(" Ln 1, Col 1 ")
        self.cursor_pos_label.setMinimumWidth(120)
        
        # Evergreen UI: Dodajemy lekki odstęp od prawej krawędzi
        self.addPermanentWidget(self.turbo_label)
        self.addPermanentWidget(self.engine_label)
        self.addPermanentWidget(self.stats_label)
        self.addPermanentWidget(self.cursor_pos_label)
        
        # Usunięcie domyślnego uchwytu zmiany rozmiaru dla czystszego wyglądu (opcjonalne)
        self.setSizeGripEnabled(False)

    def update_info(self):
        """Aktualizuje licznik znaków, pozycję kursora oraz status Turbo."""
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return

        # Pozycja kursora i statystyki
        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        chars = len(editor.toPlainText())
        
        # Tłumaczenia
        tr = self.main_window.lang_handler.tr
        ln_txt = tr("label_line") if tr("label_line") != "label_line" else "Ln"
        col_txt = tr("label_column") if tr("label_column") != "label_column" else "Col"
        sym_txt = tr("label_symbols") if tr("label_symbols") != "label_symbols" else "Symbols"

        self.cursor_pos_label.setText(f" {ln_txt} {line}, {col_txt} {col} ")
        self.stats_label.setText(f" {sym_txt}: {chars} ")
        
        # Aktualizacja statusu Turbo Mode
        if hasattr(editor, 'is_turbo_mode') and editor.is_turbo_mode:
            self.turbo_label.setText(" TURBO ")
        else:
            self.turbo_label.setText("")

    def set_engine_status(self, available):
        """Aktualizuje wizualny status silnika C++."""
        if available:
            self.engine_label.setText(" Engine: C++ ")
            self.engine_label.setProperty("engineState", "cpp")
        else:
            self.engine_label.setText(" Engine: Python ")
            self.engine_label.setProperty("engineState", "python")
        self.style().unpolish(self.engine_label)
        self.style().polish(self.engine_label)

    def retranslate_ui(self):
        """Odświeża teksty po zmianie języka."""
        self.update_info()
        tr = self.main_window.lang_handler.tr
        # Sprawdzamy, czy aktualnie nie ma ważnego komunikatu systemowego
        current = self.currentMessage()
        if not current or current == "Ready" or current == tr("status_ready"):
            self.showMessage(tr("status_ready"))
