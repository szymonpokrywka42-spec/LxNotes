from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QCheckBox, QLabel
from PyQt6.QtGui import QTextCursor, QTextDocument
from PyQt6.QtCore import Qt

try:
    import lx_engine
except Exception:
    lx_engine = None

class FindReplaceDialog(QDialog):
    _CPP_FIND_FASTPATH_MAX_CHARS = 2_000_000
    _CPP_REPLACE_COUNT_MAX_CHARS = 2_000_000

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

    def _find_flags(self, include_whole_words=True):
        flags = QTextDocument.FindFlag(0)
        if self.case_cb.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if include_whole_words and self.words_cb.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        return flags

    @staticmethod
    def _is_word_char(ch):
        return ch.isalnum() or ch == "_" or ord(ch) > 127

    def _matches_whole_word(self, document, start, end):
        if start > 0 and self._is_word_char(document.characterAt(start - 1)):
            return False
        if end < document.characterCount() and self._is_word_char(document.characterAt(end)):
            return False
        return True

    def _cpp_find_next_position(self, editor, query, start_pos):
        if lx_engine is None or not hasattr(lx_engine, "find_next_position"):
            return None

        # Avoid full-buffer copy to Python str on very large documents.
        # For huge files, Qt incremental find path is typically cheaper.
        try:
            if editor.document().characterCount() > self._CPP_FIND_FASTPATH_MAX_CHARS:
                return None
        except Exception:
            pass

        try:
            position = lx_engine.find_next_position(
                editor.toPlainText(),
                query,
                self.case_cb.isChecked(),
                self.words_cb.isChecked(),
                start_pos,
                True,
            )
        except Exception:
            return None

        try:
            position = int(position)
        except (TypeError, ValueError):
            return None

        return position if position >= 0 else None

    def _cursor_from_position(self, editor, query, position):
        document = editor.document()
        if position < 0 or position >= max(0, document.characterCount() - 1):
            return None

        cursor = QTextCursor(document)
        cursor.setPosition(position)
        cursor.setPosition(position + len(query), QTextCursor.MoveMode.KeepAnchor)

        # Defensive guard for out-of-sync positions.
        if not self._selection_matches(cursor, query):
            return None
        return cursor

    def _count_matches(self, document, query):
        if not query:
            return 0

        flags = self._find_flags(include_whole_words=False)
        search_cursor = QTextCursor(document)
        search_cursor.setPosition(0)
        count = 0

        while True:
            found = document.find(query, search_cursor, flags)
            if found.isNull():
                break
            if self.words_cb.isChecked() and not self._matches_whole_word(
                document, found.selectionStart(), found.selectionEnd()
            ):
                search_cursor = QTextCursor(found)
                continue

            count += 1
            search_cursor = QTextCursor(found)

        return count

    def _replace_all_qt(self, editor, find_text, replace_text):
        document = editor.document()
        flags = self._find_flags(include_whole_words=False)
        search_cursor = QTextCursor(document)
        search_cursor.setPosition(0)

        replace_cursor = QTextCursor(document)
        replace_cursor.beginEditBlock()
        replaced_count = 0

        try:
            while True:
                found = document.find(find_text, search_cursor, flags)
                if found.isNull():
                    break
                if self.words_cb.isChecked() and not self._matches_whole_word(
                    document, found.selectionStart(), found.selectionEnd()
                ):
                    search_cursor = QTextCursor(found)
                    continue

                found.insertText(replace_text)
                replaced_count += 1
                search_cursor = found
        finally:
            replace_cursor.endEditBlock()

        return replaced_count

    def _replace_document_text(self, editor, new_text):
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(new_text)
        cursor.endEditBlock()
        editor.setTextCursor(cursor)

    def _find_next_cursor(self, editor, query):
        document = editor.document()
        current_cursor = editor.textCursor()
        start_pos = current_cursor.selectionEnd() if current_cursor.hasSelection() else current_cursor.position()
        flags = self._find_flags(include_whole_words=False)

        def search_from(position):
            search_cursor = QTextCursor(document)
            search_cursor.setPosition(position)
            while True:
                found = document.find(query, search_cursor, flags)
                if found.isNull():
                    return found
                if not self.words_cb.isChecked() or self._matches_whole_word(
                    document, found.selectionStart(), found.selectionEnd()
                ):
                    return found
                search_cursor = QTextCursor(found)

        found = search_from(start_pos)
        if not found.isNull():
            return found
        if start_pos <= 0:
            return found

        return search_from(0)

    def _selection_matches(self, cursor, query):
        if not cursor.hasSelection():
            return False

        selected_text = cursor.selectedText()
        if self.case_cb.isChecked():
            text_matches = selected_text == query
        else:
            text_matches = selected_text.casefold() == query.casefold()

        if not text_matches:
            return False

        if not self.words_cb.isChecked():
            return True

        document = cursor.document()
        return self._matches_whole_word(document, cursor.selectionStart(), cursor.selectionEnd())

    def find_next(self):
        editor = self.em.get_current_editor()
        query = self.find_input.text()
        if not editor or not query:
            return

        current_cursor = editor.textCursor()
        start_pos = current_cursor.selectionEnd() if current_cursor.hasSelection() else current_cursor.position()
        cpp_pos = self._cpp_find_next_position(editor, query, start_pos)
        found = None
        if cpp_pos is not None:
            found = self._cursor_from_position(editor, query, cpp_pos)

        if found is None:
            found = self._find_next_cursor(editor, query)

        if found.isNull():
            return

        editor.setTextCursor(found)
        editor.ensureCursorVisible()

    def handle_replace(self):
        editor = self.em.get_current_editor()
        if not editor:
            return
        
        cursor = editor.textCursor()
        query = self.find_input.text()
        if cursor.hasSelection() and self._selection_matches(cursor, query):
            cursor.insertText(self.replace_input.text())
            self.main_window.console_logic.log("Replaced occurrence.", "ACTION")
        
        self.find_next()

    def handle_replace_all(self):
        editor = self.em.get_current_editor()
        if not editor:
            return
        
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        if not find_text:
            return

        cpp_result = None
        document = editor.document()
        doc_chars = max(0, document.characterCount() - 1)
        original_text = None

        # For huge docs avoid the extra pre-count pass; it is expensive and not
        # required for correctness when the C++ replace path is available.
        large_doc_skip_count = doc_chars > self._CPP_REPLACE_COUNT_MAX_CHARS
        pre_match_count = None if large_doc_skip_count else self._count_matches(document, find_text)
        if lx_engine is not None and hasattr(lx_engine, "replace_all_with_options"):
            try:
                original_text = editor.toPlainText()
                cpp_result = lx_engine.replace_all_with_options(
                    original_text,
                    find_text,
                    replace_text,
                    self.case_cb.isChecked(),
                    self.words_cb.isChecked(),
                )
            except Exception:
                cpp_result = None

        if isinstance(cpp_result, str):
            if original_text is not None and cpp_result == original_text:
                self.main_window.console_logic.log("Replace All: no matches found.", "INFO")
                return

            self._replace_document_text(editor, cpp_result)
            editor.ensureCursorVisible()
            if large_doc_skip_count:
                self.main_window.console_logic.log("Replace All completed.", "SUCCESS")
            else:
                self.main_window.console_logic.log(
                    f"Replace All completed ({pre_match_count} matches).",
                    "SUCCESS",
                )
            return

        match_count = pre_match_count if pre_match_count is not None else self._count_matches(document, find_text)
        if match_count == 0:
            self.main_window.console_logic.log("Replace All: no matches found.", "INFO")
            return

        replaced_count = self._replace_all_qt(editor, find_text, replace_text)
        if replaced_count:
            editor.ensureCursorVisible()
            self.main_window.console_logic.log(
                f"Replace All completed ({replaced_count} matches).",
                "SUCCESS",
            )
        else:
            self.main_window.console_logic.log("Replace All: no matches found.", "INFO")
