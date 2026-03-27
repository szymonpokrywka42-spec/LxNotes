from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QTextCharFormat, QFont, QColor, QTextOption
from PyQt6.QtCore import Qt
import math

try:
    import lx_engine
    _ENGINE_AVAILABLE = True
except Exception:
    lx_engine = None
    _ENGINE_AVAILABLE = False

class EditorTab(QTextEdit):
    def __init__(self, console=None):
        super().__init__()
        self.console = console  # Referencja do console_logic
        self.is_turbo_mode = False  # Flaga dla silnika C++ / High Performance
        self.file_encoding = "utf-8"
        self.large_file_mode = False
        self._large_content = ""
        self._large_chunk_size = 0
        self._large_chunk_index = 0
        self._large_chunk_count = 0
        self._large_chunk_lines = 4000
        self._switching_chunk = False
        self._large_buffer_handle = -1
        self._large_virtual_chars = 0
        self._large_chunk_cache = {}
        self._large_chunk_cache_order = []
        self._large_chunk_cache_limit = 3
        self._large_chunk_cache_char_budget = 5_000_000
        self._large_chunk_cache_chars = 0
        self._last_scroll_value = 0
        self._large_line_offsets = []
        self._large_line_count = 0
        self._large_ro_hint_shown = False
        self.safe_edit_mode = False
        self._safe_edit_snapshot = ""
        self._safe_paste_limit = 200_000

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

    def enable_large_file_mode(self, content: str, chunk_size: int = None):
        """Enable chunked read-only viewer mode for ultra-large texts."""
        self.large_file_mode = True
        self._large_chunk_lines = self._recommend_chunk_lines(len(content))
        self.setReadOnly(True)
        self.set_turbo_mode(True)
        self._last_scroll_value = 0
        self._large_chunk_cache = {}
        self._large_chunk_cache_order = []
        self._large_chunk_cache_chars = 0
        self._large_line_offsets = []
        self._large_line_count = 0

        using_engine_buffer = False
        if _ENGINE_AVAILABLE and hasattr(lx_engine, "create_text_buffer"):
            try:
                self._large_buffer_handle = int(lx_engine.create_text_buffer(content))
                info = lx_engine.get_text_buffer_info(self._large_buffer_handle, self._large_chunk_lines)
                self._large_chunk_count = int(info.get("chunk_count", 1))
                self._large_virtual_chars = int(info.get("chars", len(content)))
                self._large_chunk_index = 0
                self._large_content = ""
                self._large_line_count = int(info.get("line_count", 0))
                using_engine_buffer = True
            except Exception as e:
                self._large_buffer_handle = -1
                if self.console:
                    self.console.log(f"Large viewer C++ buffer unavailable: {e}", "WARN")

        if not using_engine_buffer:
            self._large_content = content
            effective_chunk_size = self._recommend_chunk_size(len(content)) if chunk_size is None else int(chunk_size)
            self._large_chunk_size = max(100_000, effective_chunk_size)
            self._large_chunk_count = max(1, math.ceil(len(content) / self._large_chunk_size))
            self._large_virtual_chars = len(content)
            self._large_chunk_index = 0

        self._load_large_chunk(0)

        try:
            self.verticalScrollBar().valueChanged.disconnect(self._on_large_scroll)
        except Exception:
            pass
        self.verticalScrollBar().valueChanged.connect(self._on_large_scroll)

        if self.console:
            self.console.log(
                f"LARGE VIEWER MODE ACTIVE: chars={self._large_virtual_chars}, chunks={self._large_chunk_count}",
                "ENGINE",
            )

    def disable_large_file_mode(self):
        if _ENGINE_AVAILABLE and self._large_buffer_handle >= 0 and hasattr(lx_engine, "release_text_buffer"):
            try:
                lx_engine.release_text_buffer(self._large_buffer_handle)
            except Exception:
                pass
        self.large_file_mode = False
        self._large_content = ""
        self._large_chunk_size = 0
        self._large_chunk_index = 0
        self._large_chunk_count = 0
        self._large_buffer_handle = -1
        self._large_virtual_chars = 0
        self._large_chunk_cache = {}
        self._large_chunk_cache_order = []
        self._large_chunk_cache_chars = 0
        self._last_scroll_value = 0
        self._large_line_offsets = []
        self._large_line_count = 0
        try:
            self.verticalScrollBar().valueChanged.disconnect(self._on_large_scroll)
        except Exception:
            pass
        self.setReadOnly(False)

    def get_virtual_char_count(self) -> int:
        if self.large_file_mode:
            return self._large_virtual_chars
        return max(0, self.document().characterCount() - 1)

    def get_full_text(self) -> str:
        if self.large_file_mode:
            if _ENGINE_AVAILABLE and self._large_buffer_handle >= 0 and hasattr(lx_engine, "get_text_buffer_full"):
                try:
                    return str(lx_engine.get_text_buffer_full(self._large_buffer_handle))
                except Exception:
                    pass
            return self._large_content
        return self.toPlainText()

    def get_large_viewer_label(self) -> str:
        if not self.large_file_mode:
            return ""
        return f"VIEW {self._large_chunk_index + 1}/{self._large_chunk_count} RO"

    def enable_safe_edit_mode(self, snapshot_text: str = ""):
        self.safe_edit_mode = True
        self._safe_edit_snapshot = snapshot_text if isinstance(snapshot_text, str) else ""
        if self.console:
            self.console.log("Safe Edit Mode enabled.", "INFO")

    def disable_safe_edit_mode(self):
        self.safe_edit_mode = False
        self._safe_edit_snapshot = ""

    def quick_revert_safe_edit(self) -> bool:
        if not self.safe_edit_mode or not isinstance(self._safe_edit_snapshot, str):
            return False
        self.setPlainText(self._safe_edit_snapshot)
        self.document().setModified(False)
        if self.console:
            self.console.log("Safe Edit Mode: content reverted to snapshot.", "INFO")
        return True

    def _load_large_chunk(self, index: int):
        if not self.large_file_mode:
            return
        idx = max(0, min(index, self._large_chunk_count - 1))
        if idx == self._large_chunk_index and self.document().characterCount() > 1:
            self._prefetch_large_chunk(idx + 1)
            self._prefetch_large_chunk(idx - 1)
            return
        self._switching_chunk = True
        self._large_chunk_index = idx

        chunk_text = self._get_chunk_text_cached(idx)

        self.setPlainText(chunk_text)
        self.document().setModified(False)
        cursor = self.textCursor()
        cursor.setPosition(0)
        self.setTextCursor(cursor)
        self._switching_chunk = False
        self._prefetch_large_chunk(idx + 1)
        self._prefetch_large_chunk(idx - 1)

    def _fetch_large_chunk_text(self, idx: int) -> str:
        chunk_text = ""
        if _ENGINE_AVAILABLE and self._large_buffer_handle >= 0 and hasattr(lx_engine, "get_text_buffer_chunk"):
            try:
                chunk = lx_engine.get_text_buffer_chunk(self._large_buffer_handle, idx, self._large_chunk_lines)
                chunk_text = str(chunk.get("text", ""))
            except Exception:
                chunk_text = ""
        if not chunk_text and self._large_content:
            start = idx * self._large_chunk_size
            end = min(len(self._large_content), start + self._large_chunk_size)
            chunk_text = self._large_content[start:end]
        return chunk_text

    def _cache_large_chunk(self, idx: int, chunk_text: str):
        previous = self._large_chunk_cache.get(idx)
        if previous is not None:
            self._large_chunk_cache_chars -= len(previous)
        self._large_chunk_cache[idx] = chunk_text
        self._large_chunk_cache_chars += len(chunk_text)
        if idx in self._large_chunk_cache_order:
            self._large_chunk_cache_order.remove(idx)
        self._large_chunk_cache_order.append(idx)

        while (
            len(self._large_chunk_cache_order) > self._large_chunk_cache_limit
            or self._large_chunk_cache_chars > self._large_chunk_cache_char_budget
        ):
            stale_idx = self._large_chunk_cache_order.pop(0)
            stale = self._large_chunk_cache.pop(stale_idx, None)
            if stale is not None:
                self._large_chunk_cache_chars -= len(stale)

    def _get_chunk_text_cached(self, idx: int) -> str:
        cached = self._large_chunk_cache.get(idx)
        if cached is not None:
            if idx in self._large_chunk_cache_order:
                self._large_chunk_cache_order.remove(idx)
            self._large_chunk_cache_order.append(idx)
            return cached

        chunk_text = self._fetch_large_chunk_text(idx)
        self._cache_large_chunk(idx, chunk_text)
        return chunk_text

    def _prefetch_large_chunk(self, idx: int):
        if not self.large_file_mode:
            return
        if idx < 0 or idx >= self._large_chunk_count:
            return
        if idx in self._large_chunk_cache:
            return
        chunk_text = self._fetch_large_chunk_text(idx)
        self._cache_large_chunk(idx, chunk_text)

    def _ensure_large_line_offsets(self):
        if self._large_line_offsets:
            return
        if not self._large_content:
            self._large_line_offsets = [0]
            self._large_line_count = 1
            return

        offsets = [0]
        for i, ch in enumerate(self._large_content):
            if ch == '\n' and i + 1 < len(self._large_content):
                offsets.append(i + 1)
        self._large_line_offsets = offsets
        self._large_line_count = len(offsets)

    def jump_to_large_line(self, line_num: int) -> bool:
        if not self.large_file_mode:
            return False

        try:
            target_line = int(line_num)
        except (TypeError, ValueError):
            return False
        if target_line < 1:
            return False

        chunk_index = None
        offset_in_chunk = 0

        if _ENGINE_AVAILABLE and self._large_buffer_handle >= 0 and hasattr(lx_engine, "get_text_buffer_chunk_for_line"):
            try:
                line_meta = lx_engine.get_text_buffer_chunk_for_line(
                    self._large_buffer_handle,
                    target_line,
                    self._large_chunk_lines,
                )
                chunk_index = int(line_meta.get("chunk_index", 0))
                start_line = int(line_meta.get("start_line", 1))
                if target_line < start_line:
                    return False
                offset_in_chunk = target_line - start_line
            except Exception:
                return False
        else:
            self._ensure_large_line_offsets()
            if target_line > self._large_line_count or self._large_chunk_size <= 0:
                return False
            char_offset = self._large_line_offsets[target_line - 1]
            chunk_index = min(self._large_chunk_count - 1, char_offset // self._large_chunk_size)
            chunk_start = chunk_index * self._large_chunk_size
            chunk_text = self._get_chunk_text_cached(chunk_index)
            local_offset = max(0, char_offset - chunk_start)
            offset_in_chunk = chunk_text[:local_offset].count('\n')

        self._load_large_chunk(chunk_index)
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        if offset_in_chunk > 0:
            cursor.movePosition(
                cursor.MoveOperation.Down,
                cursor.MoveMode.MoveAnchor,
                offset_in_chunk,
            )
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        return True

    def _on_large_scroll(self, value: int):
        if not self.large_file_mode or self._switching_chunk:
            return
        sb = self.verticalScrollBar()
        max_v = sb.maximum()
        min_v = sb.minimum()
        if max_v <= min_v:
            return

        # Seamless chunk switching at scroll edges.
        if value >= max_v - 1 and self._large_chunk_index < self._large_chunk_count - 1:
            self._load_large_chunk(self._large_chunk_index + 1)
            span = max(3, max_v - min_v)
            sb.setValue(min_v + max(1, int(span * 0.15)))
        elif value <= min_v + 1 and self._large_chunk_index > 0:
            self._load_large_chunk(self._large_chunk_index - 1)
            span = max(3, max_v - min_v)
            sb.setValue(max(sb.minimum() + 1, sb.maximum() - max(2, int(span * 0.15))))

        self._last_scroll_value = value

    def next_large_chunk(self) -> bool:
        if not self.large_file_mode:
            return False
        if self._large_chunk_index >= self._large_chunk_count - 1:
            return False
        self._load_large_chunk(self._large_chunk_index + 1)
        return True

    def previous_large_chunk(self) -> bool:
        if not self.large_file_mode:
            return False
        if self._large_chunk_index <= 0:
            return False
        self._load_large_chunk(self._large_chunk_index - 1)
        return True

    @staticmethod
    def _recommend_chunk_size(total_chars: int) -> int:
        if total_chars >= 100_000_000:
            return 4_000_000
        if total_chars >= 40_000_000:
            return 3_000_000
        if total_chars >= 15_000_000:
            return 2_000_000
        if total_chars >= 8_000_000:
            return 1_500_000
        return 1_000_000

    @staticmethod
    def _recommend_chunk_lines(total_chars: int) -> int:
        if total_chars >= 100_000_000:
            return 10000
        if total_chars >= 40_000_000:
            return 7000
        if total_chars >= 15_000_000:
            return 5000
        return 4000

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

    def keyPressEvent(self, event):
        if self.large_file_mode and self.isReadOnly():
            key = event.key()
            nav_keys = {
                Qt.Key.Key_Up,
                Qt.Key.Key_Down,
                Qt.Key.Key_Left,
                Qt.Key.Key_Right,
                Qt.Key.Key_PageUp,
                Qt.Key.Key_PageDown,
                Qt.Key.Key_Home,
                Qt.Key.Key_End,
            }
            if key not in nav_keys and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                if self.console and not self._large_ro_hint_shown:
                    self.console.log(
                        "Large Viewer Mode is read-only. Use 'Load Full Editable' to edit this file.",
                        "INFO",
                    )
                    self._large_ro_hint_shown = True
                event.ignore()
                return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        if self.safe_edit_mode and source and source.hasText():
            incoming = source.text()
            if isinstance(incoming, str) and len(incoming) > self._safe_paste_limit:
                if self.console:
                    self.console.log(
                        f"Safe Edit Mode blocked huge paste ({len(incoming)} chars).",
                        "WARN",
                    )
                return
        super().insertFromMimeData(source)

    def __del__(self):
        try:
            if self.large_file_mode:
                self.disable_large_file_mode()
        except Exception:
            pass
