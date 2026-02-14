import os
import sys
import ctypes
try:
    import chardet  # pip install chardet
except Exception:
    chardet = None
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt
from core.file.recent_files import RecentFiles

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

                preferred_encoding = ""
                confidence = 0.0
                if chardet:
                    try:
                        detection = chardet.detect(raw_data)
                        preferred_encoding = (detection.get("encoding") or "").lower()
                        confidence = float(detection.get("confidence") or 0.0)
                        # Dla niskiej pewności nie blokujemy kolejności fallbacków.
                        if preferred_encoding and confidence < 0.80:
                            self.log_signal.emit(
                                f"Low encoding confidence ({confidence*100:.1f}%). Ignoring preferred='{preferred_encoding}'.",
                                "WARN",
                            )
                            preferred_encoding = ""
                        if preferred_encoding:
                            self.log_signal.emit(
                                f"Detecting encoding for {os.path.basename(self.path)}: {preferred_encoding} ({confidence*100:.1f}%)",
                                "INFO",
                            )
                    except Exception:
                        preferred_encoding = ""

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
        if not editor: return

        path = getattr(editor, 'file_path', None)
        if not path:
            self.save_file_as()
        else:
            self._async_save(path, editor.toPlainText(), editor)

    def save_file_as(self):
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor: return

        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save File As", "", "Text Files (*.txt);;All Files (*)"
        )
        if not path: return
        self._async_save(path, editor.toPlainText(), editor, is_as=True)

    def _async_save(self, path, content, editor, is_as=False):
        self.console.log(f"Starting async save to: {path}", "FILE")
        progress_dialog = self._show_progress(f"Zapisywanie: {os.path.basename(path)}...")
        
        worker_id = f"save_{path}"
        worker = FileWorker('save', path, content)
        self._active_workers[worker_id] = worker
        
        worker.progress.connect(progress_dialog.setValue)
        worker.log_signal.connect(self.console.log)

        def on_done():
            editor.file_path = path
            if is_as:
                idx = self.main_window.editor_manager.tab_widget.indexOf(editor)
                self.main_window.editor_manager.tab_widget.setTabText(idx, os.path.basename(path))
            
            editor.document().setModified(False)
            self.main_window.editor_manager.handle_text_changed(editor)
            
            self.recent_files.add_file(path)
            self.main_window.statusBar().showMessage(f"Zapisano: {path}", 2000)
            self.console.log(f"Save completed: {path}", "SUCCESS")
            progress_dialog.close()
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        worker.finished.connect(on_done)
        worker.error.connect(lambda err: self._handle_error(err))
        worker.start()

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
