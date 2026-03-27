import os
import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QAction
from PyQt6.QtWidgets import QStatusBar, QLabel, QMenu, QApplication


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class LxStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("lxStatusBar")
        self.main_window = parent 
        self._status_mode = "advanced"
        self._insights_cache = {
            "path": "",
            "size_bytes": 0,
            "mtime_ns": None,
            "dirty": None,
            "buffer_chars": None,
            "checked_at": 0.0,
        }
        self._insights_cache_ttl = 1.0
        
        # 1. Status Silnika (Engine)
        self.engine_label = QLabel(" PY ")
        self.engine_label.setObjectName("engineStatusLabel")
        self.engine_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 2. Status trybu pracy
        self.turbo_label = QLabel("") 
        self.turbo_label.setObjectName("turboStatusLabel")
        self.turbo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.turbo_label.setMinimumWidth(64)
        
        # 3. Statystyki symboli
        self.stats_label = ClickableLabel(" Ch 0 ")
        self.stats_label.setObjectName("statsStatusLabel")
        self.stats_label.setMinimumWidth(90)
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 4. Smart insights
        self.insights_label = QLabel(" 0B | n/a ")
        self.insights_label.setObjectName("insightsStatusLabel")
        self.insights_label.setMinimumWidth(130)
        self.insights_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 5. Kodowanie pliku
        self.encoding_label = ClickableLabel(" UTF-8 ")
        self.encoding_label.setObjectName("encodingStatusLabel")
        self.encoding_label.setMinimumWidth(80)
        self.encoding_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 6. Pozycja kursora (Ln, Col)
        self.cursor_pos_label = ClickableLabel(" Ln 1:1 ")
        self.cursor_pos_label.setObjectName("cursorStatusLabel")
        self.cursor_pos_label.setMinimumWidth(95)
        self.cursor_pos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Evergreen UI: Dodajemy lekki odstęp od prawej krawędzi
        self.addPermanentWidget(self.turbo_label)
        self.addPermanentWidget(self.engine_label)
        self.addPermanentWidget(self.stats_label)
        self.addPermanentWidget(self.insights_label)
        self.addPermanentWidget(self.encoding_label)
        self.addPermanentWidget(self.cursor_pos_label)

        self.stats_label.clicked.connect(self._show_stats_actions)
        self.encoding_label.clicked.connect(self._show_encoding_actions)
        self.cursor_pos_label.clicked.connect(self._show_cursor_actions)
        
        # Usunięcie domyślnego uchwytu zmiany rozmiaru dla czystszego wyglądu (opcjonalne)
        self.setSizeGripEnabled(False)

    def set_display_mode(self, mode):
        normalized_mode = "advanced" if str(mode).lower() == "advanced" else "simple"
        self._status_mode = normalized_mode
        is_advanced = normalized_mode == "advanced"
        self.stats_label.setVisible(is_advanced)
        self.insights_label.setVisible(is_advanced)

    def get_display_mode(self):
        return self._status_mode

    def update_info(self):
        """Aktualizuje licznik znaków, pozycję kursora oraz status Turbo."""
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return

        # Pozycja kursora i statystyki
        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        # O(1) counter from Qt document is much cheaper on huge files.
        if hasattr(editor, "get_virtual_char_count"):
            chars = editor.get_virtual_char_count()
        else:
            chars = max(0, editor.document().characterCount() - 1)
        encoding = getattr(editor, "file_encoding", "utf-8")
        
        # Tłumaczenia
        tr = self.main_window.lang_handler.tr
        ln_txt = tr("label_line") if tr("label_line") != "label_line" else "Ln"
        sym_txt = tr("label_symbols") if tr("label_symbols") != "label_symbols" else "Ch"
        chars_label = self._format_compact_number(chars)
        if sym_txt.lower().startswith("sym"):
            sym_txt = "Ch"

        self.cursor_pos_label.setText(f" {ln_txt} {line}:{col} ")
        self.stats_label.setText(f" {sym_txt} {chars_label} ")
        self.encoding_label.setText(f" {str(encoding).upper()} ")
        self.insights_label.setText(f" {self._build_insights(editor, chars)} ")
        
        # Aktualizacja statusu Turbo Mode
        if getattr(editor, "large_file_mode", False):
            label = " VIEW "
            if hasattr(editor, "get_large_viewer_label"):
                chunk_label = editor.get_large_viewer_label()
                if chunk_label:
                    label = f" {chunk_label} "
            self.turbo_label.setText(label)
        elif hasattr(editor, 'is_turbo_mode') and editor.is_turbo_mode:
            self.turbo_label.setText(" TURBO ")
        elif getattr(editor, "safe_edit_mode", False):
            self.turbo_label.setText(" SAFE ")
        else:
            self.turbo_label.setText("")

    @staticmethod
    def _format_compact_number(value):
        num = max(0, int(value))
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        if num >= 1_000:
            return f"{num / 1_000:.1f}K"
        return str(num)

    def _build_insights(self, editor, chars):
        file_path = getattr(editor, "file_path", "")
        size_bytes = self._get_file_size(editor, file_path, chars)
        if size_bytes <= 0:
            # Approximation for unsaved buffers (UTF-8 rough estimate).
            size_bytes = int(chars)

        if size_bytes >= 1024 * 1024:
            size_label = f"{size_bytes / (1024 * 1024):.1f}MB"
        elif size_bytes >= 1024:
            size_label = f"{size_bytes / 1024:.0f}KB"
        else:
            size_label = f"{size_bytes}B"

        conf = float(getattr(editor, "file_encoding_confidence", 0.0) or 0.0)
        conf_label = f"{int(conf * 100)}%" if conf > 0 else "n/a"
        _ = chars  # maintained for API compatibility
        return f"{size_label} | {conf_label}"

    def _get_file_size(self, editor, file_path, chars=0):
        if not file_path:
            return 0

        now = time.monotonic()
        cache = self._insights_cache
        document = editor.document() if hasattr(editor, "document") else None
        dirty = bool(document.isModified()) if document else False
        buffer_chars = max(0, int(chars))

        # Dirty buffers change frequently, so we keep the size estimate local and avoid os.stat().
        if dirty:
            cache_valid = (
                cache["path"] == file_path
                and cache.get("dirty") == dirty
                and cache.get("buffer_chars") == buffer_chars
            )
            if cache_valid:
                return cache["size_bytes"]

            cache.update(
                path=file_path,
                size_bytes=buffer_chars,
                mtime_ns=None,
                dirty=dirty,
                buffer_chars=buffer_chars,
                checked_at=now,
            )
            return buffer_chars

        cache_valid = (
            cache["path"] == file_path
            and cache.get("dirty") == dirty
            and cache.get("mtime_ns") is not None
            and now - cache["checked_at"] < self._insights_cache_ttl
        )
        if cache_valid:
            return cache["size_bytes"]

        try:
            stat = os.stat(file_path)
        except OSError:
            cache.update(
                path=file_path,
                size_bytes=0,
                mtime_ns=None,
                dirty=dirty,
                buffer_chars=None,
                checked_at=now,
            )
            return 0

        size_bytes = int(stat.st_size)
        mtime_ns = getattr(stat, "st_mtime_ns", None)
        if cache["path"] == file_path and cache.get("mtime_ns") == mtime_ns and cache.get("dirty") == dirty:
            cache.update(checked_at=now)
            return cache["size_bytes"]

        cache.update(
            path=file_path,
            size_bytes=size_bytes,
            mtime_ns=mtime_ns,
            dirty=dirty,
            buffer_chars=None,
            checked_at=now,
        )
        return size_bytes

    def set_engine_status(self, available):
        """Aktualizuje wizualny status silnika C++."""
        if available:
            self.engine_label.setText(" C++ ")
            self.engine_label.setProperty("engineState", "cpp")
        else:
            self.engine_label.setText(" PY ")
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

    def _show_stats_actions(self):
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return

        menu = QMenu(self)
        copy_action = QAction("Copy symbols count", self)
        select_all_action = QAction("Select all text", self)
        if hasattr(editor, "get_virtual_char_count"):
            copy_action.triggered.connect(lambda: QApplication.clipboard().setText(str(editor.get_virtual_char_count())))
        else:
            copy_action.triggered.connect(lambda: QApplication.clipboard().setText(str(max(0, editor.document().characterCount() - 1))))
        select_all_action.triggered.connect(editor.selectAll)
        menu.addAction(copy_action)
        menu.addAction(select_all_action)
        menu.exec(QCursor.pos())

    def _show_encoding_actions(self):
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return

        menu = QMenu(self)
        copy_action = QAction("Copy encoding", self)
        log_action = QAction("Log encoding to console", self)
        copy_action.triggered.connect(
            lambda: QApplication.clipboard().setText(str(getattr(editor, "file_encoding", "utf-8")))
        )
        log_action.triggered.connect(
            lambda: self.main_window.console_logic.log(
                f"Current tab encoding: {getattr(editor, 'file_encoding', 'utf-8')}",
                "INFO",
            )
        )
        menu.addAction(copy_action)
        menu.addAction(log_action)
        menu.exec(QCursor.pos())

    def _show_cursor_actions(self):
        menu = QMenu(self)
        goto_action = QAction("Go to line...", self)
        goto_action.triggered.connect(self.main_window.edit_menu.open_goto_line)
        menu.addAction(goto_action)
        menu.exec(QCursor.pos())
