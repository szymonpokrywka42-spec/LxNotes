from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QCheckBox, QLabel, QStyledItemDelegate)
from PyQt6.QtGui import QTextCursor
from PyQt6.QtCore import Qt

class FindReplaceDialog(QDialog):
    def __init__(self, parent, editor_manager):
        super().__init__(parent)
        self.main_window = parent 
        self.em = editor_manager
        
        # UI Setup - Kompaktowy rozmiar dla panelu wyszukiwania
        self.setFixedWidth(400)
        # Ustawiamy WindowType na Tool, aby okno było lżejsze i zawsze na wierzchu edytora
        self.setWindowFlags(Qt.WindowType.Tool)
        
        self.init_ui()
        self.retranslate_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # --- SEKCJA SZUKANIA ---
        self.label_find = QLabel()
        self.label_find.setObjectName("sectionHeader")
        
        self.find_input = QLineEdit()
        self.find_input.setObjectName("ConsoleInput") # Używamy tego samego ID co w konsoli dla spójności
        
        layout.addWidget(self.label_find)
        layout.addWidget(self.find_input)
        
        # --- SEKCJA ZAMIANY ---
        self.label_replace = QLabel()
        self.label_replace.setObjectName("sectionHeader")
        
        self.replace_input = QLineEdit()
        self.replace_input.setObjectName("ConsoleInput")
        
        layout.addWidget(self.label_replace)
        layout.addWidget(self.replace_input)
        
        # --- OPCJE (Checkboxy) ---
        options_layout = QHBoxLayout()
        options_layout.setSpacing(15)
        
        self.case_cb = QCheckBox()
        self.words_cb = QCheckBox()
        
        options_layout.addWidget(self.case_cb)
        options_layout.addWidget(self.words_cb)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # --- PRZYCISKI AKCJI ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.find_btn = QPushButton()
        self.find_btn.setObjectName("primaryButton")
        self.find_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.replace_btn = QPushButton()
        self.replace_btn.setObjectName("secondaryButton")
        self.replace_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.replace_all_btn = QPushButton()
        self.replace_all_btn.setObjectName("secondaryButton")
        self.replace_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.find_btn.clicked.connect(self.find_next)
        self.replace_btn.clicked.connect(self.handle_replace)
        self.replace_all_btn.clicked.connect(self.handle_replace_all)

        btn_layout.addWidget(self.find_btn)
        btn_layout.addWidget(self.replace_btn)
        btn_layout.addWidget(self.replace_all_btn)
        layout.addLayout(btn_layout)

    def retranslate_ui(self):
        tr = self.main_window.lang_handler.tr
        self.setWindowTitle(tr("fr_title"))
        self.label_find.setText(tr("fr_label_find"))
        self.label_replace.setText(tr("fr_label_replace"))
        self.find_input.setPlaceholderText(tr("fr_placeholder_find"))
        self.replace_input.setPlaceholderText(tr("fr_placeholder_replace"))
        self.case_cb.setText(tr("fr_case_sensitive"))
        self.words_cb.setText(tr("fr_whole_words"))
        self.find_btn.setText(tr("fr_btn_find"))
        self.replace_btn.setText(tr("fr_btn_replace"))
        self.replace_all_btn.setText(tr("fr_btn_replace_all"))

    def find_next(self):
        editor = self.em.get_current_editor()
        query = self.find_input.text()
        if not editor or not query: return
        
        # Próba użycia silnika C++ dla wydajności
        try:
            import lx_engine
            results = lx_engine.find_all(
                editor.toPlainText(), query, 
                self.case_cb.isChecked(), 
                self.words_cb.isChecked()
            )
            if results:
                cursor = editor.textCursor()
                current_pos = cursor.position()
                # Znajdź następne wystąpienie po kursorze
                next_pos = next((p for p in results if p > current_pos), results[0])
                cursor.setPosition(next_pos)
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(query))
                editor.setTextCursor(cursor)
                editor.ensureCursorVisible()
        except (ImportError, AttributeError):
            # Fallback do standardowego mechanizmu Qt
            flags = QTextCursor.FindFlag(0)
            if self.case_cb.isChecked(): flags |= QTextCursor.FindFlag.FindCaseSensitively
            if self.words_cb.isChecked(): flags |= QTextCursor.FindFlag.FindWholeWords
            
            if not editor.find(query, flags):
                # Jeśli nie znaleziono od kursora do końca, szukaj od początku (wrap around)
                cursor = editor.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                editor.setTextCursor(cursor)
                editor.find(query, flags)

    def handle_replace(self):
        editor = self.em.get_current_editor()
        if not editor: return
        
        cursor = editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText().lower() == self.find_input.text().lower():
            cursor.insertText(self.replace_input.text())
            self.main_window.console_logic.log("Replaced occurrence.", "ACTION")
        
        self.find_next()

    def handle_replace_all(self):
        editor = self.em.get_current_editor()
        if not editor: return
        
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        if not find_text: return

        try:
            import lx_engine
            new_text = lx_engine.replace_all(
                editor.toPlainText(),
                find_text,
                replace_text,
                self.case_cb.isChecked()
            )
            editor.setPlainText(new_text)
            self.main_window.console_logic.log(f"All occurrences of '{find_text}' replaced via C++.", "SUCCESS")
        except (ImportError, AttributeError):
            content = editor.toPlainText()
            if self.case_cb.isChecked():
                new_content = content.replace(find_text, replace_text)
            else:
                import re
                insensitive_replace = re.compile(re.escape(find_text), re.IGNORECASE)
                new_content = insensitive_replace.sub(replace_text, content)
            editor.setPlainText(new_content)
            self.main_window.console_logic.log("Replace All (Python Fallback) executed.", "SUCCESS")