import os
import sys
import ctypes
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt
from core.file.recent_files import RecentFiles

# --- IMPORT LxCharset (lokalny moduł projektu) ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LXCHARSET_ROOT = os.path.join(PROJECT_ROOT, "LxCharset", "Module", "LxCharset")
LXCHARSET_CORE_PY = os.path.join(LXCHARSET_ROOT, "core", "python")
LXCHARSET_LOGICS_PY = os.path.join(LXCHARSET_ROOT, "logics", "python")
for _p in (LXCHARSET_CORE_PY, LXCHARSET_LOGICS_PY):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from lxcharset import module as lxcharset_module, feedback as lxcharset_feedback
    LXCHARSET_AVAILABLE = True
except Exception:
    lxcharset_module = None
    lxcharset_feedback = None
    LXCHARSET_AVAILABLE = False

# --- FIX DLA LINUXA (Symbolic C++ Optimization) ---
if sys.platform.startswith('linux'):
    try:
        # Umożliwia poprawne ładowanie symboli C++ między modułami
        sys.setdlopenflags(sys.getdlopenflags() | ctypes.RTLD_GLOBAL)
    except Exception:
        pass

# --- IMPORT SILNIKA C++ ---
try:
    import lx_engine
    ENGINE_AVAILABLE = True
except ImportError:
    lx_engine = None
    ENGINE_AVAILABLE = False


def _map_feedback_level(level):
    mapping = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARN",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }
    return mapping.get(str(level).upper(), "INFO")


def _detect_preferred_encoding(raw_data, file_path, emit_log):
    preferred_encoding = ""
    confidence = 0.0

    if not LXCHARSET_AVAILABLE:
        emit_log(
            "LxCharset unavailable. Decoding will use fallback encoding order only.",
            "WARN",
        )
        return preferred_encoding, confidence

    def _worker_feedback_cb(event):
        ctx = ""
        if getattr(event, "context", None):
            ctx = " | " + ", ".join(f"{k}={v}" for k, v in event.context.items())
        emit_log(
            f"[LxCharset] {event.code}: {event.message}{ctx}",
            _map_feedback_level(event.level),
        )

    lxcharset_feedback.subscribe(_worker_feedback_cb)
    try:
        detection = lxcharset_module.detect_encoding(raw_data)
    finally:
        lxcharset_feedback.unsubscribe(_worker_feedback_cb)

    preferred_encoding = (getattr(detection, "encoding", "") or "").lower()
    confidence = float(getattr(detection, "confidence", 0.0) or 0.0)
    if preferred_encoding and confidence < 0.80:
        emit_log(
            f"Low encoding confidence ({confidence*100:.1f}%). Ignoring preferred='{preferred_encoding}'.",
            "WARN",
        )
        preferred_encoding = ""
    if preferred_encoding:
        emit_log(
            f"LxCharset detected encoding for {os.path.basename(file_path)}: "
            f"{preferred_encoding} ({confidence*100:.1f}%)",
            "INFO",
        )
    return preferred_encoding, confidence

class FileWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    log_signal = pyqtSignal(str, str)

    def __init__(self, task_type, path, content=None):
        super().__init__()
        self.task_type = task_type
        self.path = path
        self.content = content

    def run(self):
        try:
            if self.task_type == 'open':
                self.progress.emit(10)
                
                if not os.path.exists(self.path):
                    raise FileNotFoundError(f"Plik nie istnieje: {self.path}")

                with open(self.path, "rb") as f:
                    raw_data = f.read()
                
                self.progress.emit(30)

                preferred_encoding, confidence = _detect_preferred_encoding(
                    raw_data,
                    self.path,
                    self.log_signal.emit,
                )

                fallback_encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'cp1250', 'latin-1', 'iso-8859-2']
                data = None

                if ENGINE_AVAILABLE and hasattr(lx_engine, "decode_bytes"):
                    decode_result = lx_engine.decode_bytes(
                        raw_data,
                        preferred_encoding,
                        fallback_encodings,
                        True,
                    )
                    data = str(decode_result.get("text", ""))
                    used_encoding = str(decode_result.get("encoding", "unknown"))
                    used_fallback = bool(decode_result.get("used_fallback", False))
                    attempts = decode_result.get("attempts", [])

                    level = "WARN" if used_fallback else "INFO"
                    self.log_signal.emit(
                        f"Decoded using lx_engine: {used_encoding} | fallback={used_fallback} | attempts={attempts}",
                        level,
                    )
                else:
                    # Fallback do poprzedniej ścieżki Pythonowej jeśli silnik C++ jest niedostępny.
                    if preferred_encoding:
                        try:
                            data = raw_data.decode(preferred_encoding)
                        except Exception:
                            data = None

                    if data is None:
                        self.log_signal.emit("lx_engine.decode_bytes unavailable, trying Python fallback encodings...", "WARN")
                        for enc in fallback_encodings:
                            try:
                                data = raw_data.decode(enc)
                                self.log_signal.emit(f"Decoded successfully using: {enc}", "INFO")
                                break
                            except Exception:
                                continue

                    if data is None:
                        self.log_signal.emit("All decoders failed. Using UTF-8 replace mode.", "ERROR")
                        data = raw_data.decode('utf-8', errors='replace')

                self.progress.emit(60)
                
                # Integracja z silnikiem C++ dla dużych plików
                if len(data) > 50000 and ENGINE_AVAILABLE:
                    self.log_signal.emit(f"Large file detected ({len(data)} chars). Invoking lx_engine C++...", "ENGINE")
                    data = lx_engine.prepare_large_text(data)
                
                self.progress.emit(100)
                self.finished.emit(data)
            
            elif self.task_type == 'save':
                # Zapisujemy zawsze w UTF-8 (standard nowoczesnych edytorów)
                with open(self.path, "w", encoding="utf-8") as f:
                    f.write(self.content)
                self.progress.emit(100)
                self.finished.emit(self.path)
                
        except Exception as e:
            self.error.emit(str(e))
            self.log_signal.emit(f"Worker Error: {str(e)}", "CRITICAL")

class FileHandler:
    def __init__(self, main_window, autosave_interval=300):
        self.main_window = main_window
        self.console = main_window.console_logic 
        self.recent_files = RecentFiles()
        self.autosave_interval = autosave_interval

        # Timer autozapisu
        self.timer = QTimer()
        self.timer.timeout.connect(self.autosave_all)
        self.timer.start(self.autosave_interval * 1000)
        
        self._active_workers = {}

    def _show_progress(self, label):
        progress = QProgressDialog(label, "Anuluj", 0, 100, self.main_window)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)
        progress.setValue(0)
        return progress

    def go_to_line(self, line_num):
        """Logika skoku do linii zintegrowana z lx_engine i konsolą."""
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return

        if not ENGINE_AVAILABLE:
            self.console.log("C++ Engine not available for GoToLine", "ERROR")
            return

        content = editor.toPlainText()
        
        # Wywołanie nowej funkcji z C++
        offset = lx_engine.get_line_offset(content, line_num)
        
        if offset != -1:
            cursor = editor.textCursor()
            cursor.setPosition(offset)
            editor.setTextCursor(cursor)
            editor.ensureCursorVisible()
            
            self.console.log(f"Navigation: Jumped to line {line_num} (offset: {offset})", "SUCCESS")
        else:
            self.console.log(f"Navigation: Line {line_num} is out of range", "WARN")

    def open_file_by_path(self, path):
        if not os.path.exists(path):
            self.console.log(f"Session: File not found {path}", "ERROR")
            return False

        worker_id = f"open_{path}"
        worker = FileWorker('open', path)
        self._active_workers[worker_id] = worker
        
        worker.log_signal.connect(self.console.log)
        
        def on_finished(content):
            editor = self.main_window.editor_manager.new_tab(
                title=os.path.basename(path)
            )
            editor.file_path = path
            editor.setPlainText(content)
            
            if len(content) > 50000 and ENGINE_AVAILABLE:
                if hasattr(editor, 'set_turbo_mode'):
                    editor.set_turbo_mode(True)
            
            editor.document().setModified(False)
            self.main_window.editor_manager.handle_text_changed(editor)
            self.recent_files.add_file(path)
            self.console.log(f"Session: Restored {os.path.basename(path)}", "SUCCESS")
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        worker.finished.connect(on_finished)
        worker.error.connect(lambda err: self._handle_error(err))
        worker.start()
        return True

    def open_file(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self.main_window, "Open File", "", "Text Files (*.txt);;All Files (*)"
            )
            if not path: return

        self.console.log(f"Attempting to open: {path}", "FILE")
        progress_dialog = self._show_progress(f"Wczytywanie: {os.path.basename(path)}...")
        
        worker_id = f"open_{path}"
        worker = FileWorker('open', path)
        self._active_workers[worker_id] = worker
        
        worker.progress.connect(progress_dialog.setValue)
        worker.log_signal.connect(self.console.log)
        
        def on_finished(content):
            editor = self.main_window.editor_manager.new_tab(
                title=os.path.basename(path)
            )
            editor.file_path = path
            editor.setPlainText(content)
            
            if len(content) > 50000 and ENGINE_AVAILABLE:
                if hasattr(editor, 'set_turbo_mode'):
                    editor.set_turbo_mode(True)
                    self.console.log("Turbo Mode enabled.", "ENGINE")
            
            editor.document().setModified(False)
            self.main_window.editor_manager.handle_text_changed(editor)
            self.recent_files.add_file(path)
            
            progress_dialog.close()
            self.main_window.statusBar().showMessage(f"Otwarto: {path}", 3000)
            self.console.log(f"File loaded successfully: {path}", "SUCCESS")
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        worker.finished.connect(on_finished)
        worker.error.connect(lambda err: self._handle_error(err))
        worker.start()

    def save_file(self):
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return False

        path = getattr(editor, 'file_path', None)
        if not path:
            return self.save_file_as()
        else:
            return self._async_save(path, editor.toPlainText(), editor)

    def save_file_as(self):
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return False

        # Używamy instancji dialogu zamiast statycznego helpera, żeby mieć stabilne
        # zachowanie confirm-overwrite między środowiskami.
        dialog = QFileDialog(self.main_window, "Save File As")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setNameFilters(["Text Files (*.txt)", "All Files (*)"])
        dialog.setDefaultSuffix("txt")
        dialog.setOption(QFileDialog.Option.DontConfirmOverwrite, False)

        current_path = getattr(editor, 'file_path', None)
        if current_path:
            dialog.selectFile(current_path)

        if not dialog.exec():
            return False

        selected = dialog.selectedFiles()
        path = selected[0] if selected else ""
        if not path:
            return False

        # Dodatkowe, jawne potwierdzenie nadpisania dla pełnej przewidywalności.
        if os.path.exists(path):
            tr = self.main_window.lang_handler.tr if hasattr(self.main_window, "lang_handler") else lambda x: x
            title = tr("msg_unsaved_title") if tr("msg_unsaved_title") != "msg_unsaved_title" else "Confirm overwrite"
            text = f"File already exists:\n{path}\n\nOverwrite this file?"
            answer = QMessageBox.question(
                self.main_window,
                title,
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.console.log(f"Save As canceled for existing file: {path}", "INFO")
                return False

        return self._async_save(path, editor.toPlainText(), editor, is_as=True)

    def _async_save(self, path, content, editor, is_as=False):
        self.console.log(f"Starting async save to: {path}", "FILE")
        progress_dialog = self._show_progress(f"Zapisywanie: {os.path.basename(path)}...")
        
        worker_id = f"save_{path}"
        worker = FileWorker('save', path, content)
        self._active_workers[worker_id] = worker
        
        worker.progress.connect(progress_dialog.setValue)
        worker.log_signal.connect(self.console.log)

        def on_done(saved_path):
            final_path = saved_path or path
            editor.file_path = path
            if is_as:
                idx = self.main_window.editor_manager.tab_widget.indexOf(editor)
                self.main_window.editor_manager.tab_widget.setTabText(idx, os.path.basename(final_path))
            
            editor.document().setModified(False)
            self.main_window.editor_manager.handle_text_changed(editor)
            
            self.recent_files.add_file(final_path)
            self.main_window.statusBar().showMessage(f"Zapisano: {final_path}", 2000)
            self.console.log(f"Save completed: {final_path}", "SUCCESS")
            progress_dialog.close()
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        worker.finished.connect(on_done)
        worker.error.connect(lambda err: self._handle_error(err))
        worker.start()
        return True

    def _handle_error(self, err):
        self.console.log(f"Operation failed: {err}", "ERROR")
        QMessageBox.critical(self.main_window, "Błąd", err)

    def autosave_all(self):
        em = self.main_window.editor_manager
        count = 0
        for idx in range(em.tab_widget.count()):
            try:
                editor = em.tab_widget.widget(idx)
                path = getattr(editor, 'file_path', None)
                if not path:
                    continue
                
                autosave_path = f"{path}.autosave"
                with open(autosave_path, "w", encoding="utf-8") as f:
                    f.write(editor.toPlainText())
                count += 1
            except Exception as e:
                self.console.log(f"Autosave failed for tab {idx}: {str(e)}", "WARN")
        
        if count > 0:
            self.console.log(f"Autosaved {count} file(s).", "SYSTEM")
