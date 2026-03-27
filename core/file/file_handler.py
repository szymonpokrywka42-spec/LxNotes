import os
import sys
import ctypes
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt
from core.file.recent_files import RecentFiles
from core.file.operation_flows import OpenFlow, SaveFlow

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

    subscribed = False
    if hasattr(lxcharset_feedback, "subscribe"):
        lxcharset_feedback.subscribe(_worker_feedback_cb)
        subscribed = True
    try:
        detection = lxcharset_module.detect_encoding(raw_data)
    except Exception as err:
        emit_log(
            f"LxCharset detection failed ({type(err).__name__}): {err}. "
            "Falling back to decode order.",
            "WARN",
        )
        return preferred_encoding, confidence
    finally:
        if subscribed and hasattr(lxcharset_feedback, "unsubscribe"):
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

class BaseFileWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    log_signal = pyqtSignal(str, str)

    def __init__(self, path, content=None):
        super().__init__()
        self.path = path
        self.content = content
        self.used_encoding = "utf-8"
        self.encoding_confidence = 0.0
        self.save_encoding = "utf-8"

    def _should_stop(self):
        return self.isInterruptionRequested()

    def _decode_with_engine(self, raw_data, preferred_encoding, fallback_encodings):
        if not (ENGINE_AVAILABLE and hasattr(lx_engine, "decode_bytes")):
            return None
        try:
            decode_result = lx_engine.decode_bytes(
                raw_data,
                preferred_encoding,
                fallback_encodings,
                True,
            )
            data = str(decode_result.get("text", ""))
            used_encoding = str(decode_result.get("encoding", "unknown"))
            if used_encoding and used_encoding != "unknown":
                self.used_encoding = used_encoding
            used_fallback = bool(decode_result.get("used_fallback", False))
            attempts = decode_result.get("attempts", [])
            level = "WARN" if used_fallback else "INFO"
            self.log_signal.emit(
                f"Decoded using lx_engine: {used_encoding} | fallback={used_fallback} | attempts={attempts}",
                level,
            )
            return data
        except Exception as engine_error:
            # Hard failover: C++ decoder error must not crash file open path.
            self.log_signal.emit(
                f"lx_engine.decode_bytes failed ({type(engine_error).__name__}): {engine_error}. "
                "Switching to Python fallback decoders.",
                "WARN",
            )
            return None

    def _decode_with_fallbacks(self, raw_data, preferred_encoding, fallback_encodings):
        data = None
        if preferred_encoding:
            if self._should_stop():
                return None
            try:
                data = raw_data.decode(preferred_encoding)
                self.used_encoding = preferred_encoding
            except Exception:
                data = None

        if data is None:
            self.log_signal.emit("lx_engine.decode_bytes unavailable, trying Python fallback encodings...", "WARN")
            for enc in fallback_encodings:
                if self._should_stop():
                    return None
                try:
                    data = raw_data.decode(enc)
                    self.log_signal.emit(f"Decoded successfully using: {enc}", "INFO")
                    self.used_encoding = enc
                    break
                except Exception:
                    continue

        if data is None:
            self.log_signal.emit("All decoders failed. Using UTF-8 replace mode.", "ERROR")
            data = raw_data.decode("utf-8", errors="replace")
            self.used_encoding = "utf-8"
        return data

    def _optimize_large_text(self, data):
        # Integracja z silnikiem C++ dla dużych plików.
        # For ultra-large payloads skip extra transform to reduce UI lag/spikes.
        if len(data) <= 50000 or not ENGINE_AVAILABLE:
            return data
        if self._should_stop():
            return data

        if len(data) > 5_000_000:
            self.log_signal.emit(
                f"Large file detected ({len(data)} chars). Skipping prepare_large_text for smoother scrolling.",
                "ENGINE",
            )
            return data

        self.log_signal.emit(f"Large file detected ({len(data)} chars). Invoking lx_engine C++...", "ENGINE")
        try:
            prepared = lx_engine.prepare_large_text(data)
            if isinstance(prepared, str):
                return prepared
            # Defensive fallback: keep original text if engine returns unexpected type.
            self.log_signal.emit(
                f"lx_engine.prepare_large_text returned {type(prepared).__name__}; using original text.",
                "WARN",
            )
            return data
        except Exception as prep_error:
            # Hard failover: rendering optimization must not crash file open.
            self.log_signal.emit(
                f"lx_engine.prepare_large_text failed ({type(prep_error).__name__}): {prep_error}. "
                "Using original decoded text.",
                "WARN",
            )
            return data

    def _run_open_task(self):
        self.progress.emit(10)
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Plik nie istnieje: {self.path}")

        with open(self.path, "rb") as f:
            raw_data = f.read()

        if self._should_stop():
            return
        self.progress.emit(30)

        preferred_encoding, confidence = _detect_preferred_encoding(
            raw_data,
            self.path,
            self.log_signal.emit,
        )
        self.encoding_confidence = confidence
        if self._should_stop():
            return

        fallback_encodings = ["utf-8-sig", "utf-16", "utf-8", "cp1250", "iso-8859-2", "latin-1"]
        data = self._decode_with_engine(raw_data, preferred_encoding, fallback_encodings)
        if data is None:
            data = self._decode_with_fallbacks(raw_data, preferred_encoding, fallback_encodings)
        if data is None or self._should_stop():
            return

        self.progress.emit(60)
        data = self._optimize_large_text(data)

        if self._should_stop():
            return
        self.progress.emit(100)
        self.finished.emit(data)

    def _run_save_task(self):
        if self._should_stop():
            return
        target_encoding = str(getattr(self, "save_encoding", "utf-8") or "utf-8")
        try:
            with open(self.path, "w", encoding=target_encoding) as f:
                f.write(self.content)
            self.used_encoding = target_encoding
        except UnicodeEncodeError:
            # Safety fallback: never lose save operation due to unsupported chars.
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(self.content)
            self.used_encoding = "utf-8"
            self.log_signal.emit(
                f"Requested save encoding '{target_encoding}' could not encode data. Saved as UTF-8 instead.",
                "WARN",
            )
        self.progress.emit(100)
        self.finished.emit(self.path)

    def run(self):
        raise NotImplementedError


class OpenFileWorker(BaseFileWorker):
    def __init__(self, path, content=None):
        super().__init__(path=path, content=content)

    def run(self):
        try:
            if self._should_stop():
                return
            self._run_open_task()
        except Exception as e:
            self.error.emit(str(e))
            self.log_signal.emit(f"Worker Error: {str(e)}", "CRITICAL")


class SaveFileWorker(BaseFileWorker):
    def __init__(self, path, content=None):
        super().__init__(path=path, content=content)

    def run(self):
        try:
            if self._should_stop():
                return
            self._run_save_task()
        except Exception as e:
            self.error.emit(str(e))
            self.log_signal.emit(f"Worker Error: {str(e)}", "CRITICAL")


class AutosaveWorker(QThread):
    completed = pyqtSignal(int, object)

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs

    def run(self):
        saved_count = 0
        errors = []
        for tab_idx, autosave_path, content in self.jobs:
            try:
                with open(autosave_path, "w", encoding="utf-8") as file_obj:
                    file_obj.write(content)
                saved_count += 1
            except Exception as err:
                errors.append((tab_idx, str(err)))
        self.completed.emit(saved_count, errors)


def FileWorker(task_type, path, content=None):
    """Compatibility factory for existing call sites/tests."""
    kind = str(task_type or "").lower()
    if kind == "open":
        return OpenFileWorker(path=path, content=content)
    if kind == "save":
        return SaveFileWorker(path=path, content=content)
    raise ValueError(f"Unknown worker task_type: {task_type}")


class WorkerRegistry:
    def __init__(self):
        self._active = {}
        self._canceled = set()

    def add(self, worker, prefix, path):
        worker_id = f"{prefix}:{path}:{id(worker)}"
        self._active[worker_id] = worker
        return worker_id

    def find_by_prefix_path(self, prefix, path):
        needle = f"{prefix}:{path}:"
        for worker_id, worker in self._active.items():
            if worker_id.startswith(needle):
                return worker_id, worker
        return None, None

    def has_active(self, worker_id):
        return worker_id in self._active

    def remove(self, worker_id, clear_cancel=True):
        if worker_id in self._active:
            del self._active[worker_id]
        if clear_cancel:
            self._canceled.discard(worker_id)

    def mark_canceled(self, worker_id):
        self._canceled.add(worker_id)

    def is_canceled(self, worker_id):
        return worker_id in self._canceled

class FileHandler:
    def __init__(self, main_window, autosave_interval=300):
        self.main_window = main_window
        self.console = main_window.console_logic 
        self.recent_files = RecentFiles(console_logic=self.console)
        self.autosave_interval = autosave_interval

        # Timer autozapisu
        self.timer = QTimer()
        self.timer.timeout.connect(self.autosave_all)
        self.timer.start(self.autosave_interval * 1000)
        
        self._workers = WorkerRegistry()
        self._worker_factory = FileWorker
        self._open_flow = OpenFlow(self)
        self._save_flow = SaveFlow(self)
        self._autosave_worker = None

    def _tr(self, key, default):
        lang_handler = getattr(self.main_window, "lang_handler", None)
        if lang_handler and hasattr(lang_handler, "tr"):
            text = lang_handler.tr(key)
            if text != key:
                return text
        return default

    @staticmethod
    def _get_editor_text(editor):
        if hasattr(editor, "get_full_text"):
            return editor.get_full_text()
        return editor.toPlainText()

    @staticmethod
    def _get_editor_document(editor):
        document = getattr(editor, "document", None)
        if callable(document):
            try:
                return document()
            except Exception:
                return None
        return document

    @classmethod
    def _find_line_offset_qt(cls, editor, line_num):
        try:
            target_line = int(line_num)
        except (TypeError, ValueError):
            return -1

        if target_line < 1:
            return -1

        document = cls._get_editor_document(editor)
        if not document or not hasattr(document, "findBlockByLineNumber"):
            return -1

        try:
            block = document.findBlockByLineNumber(target_line - 1)
        except Exception:
            return -1

        if not block:
            return -1

        try:
            if hasattr(block, "isValid") and not block.isValid():
                return -1
            return int(block.position())
        except Exception:
            return -1

    @staticmethod
    def _resolve_save_encoding(editor, save_policy="preserve"):
        policy = str(save_policy or "preserve").lower()
        if policy == "utf-8":
            return "utf-8"
        encoding = str(getattr(editor, "file_encoding", "") or "").strip().lower()
        if encoding and encoding != "unknown":
            return encoding
        return "utf-8"

    def _show_progress(self, label):
        progress = QProgressDialog(label, self._tr("btn_cancel", "Cancel"), 0, 100, self.main_window)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)
        progress.setValue(0)
        return progress

    def _register_worker(self, worker, prefix, path):
        return self._workers.add(worker, prefix, path)

    def _find_active_worker(self, prefix, path):
        return self._workers.find_by_prefix_path(prefix, path)

    def _cleanup_worker(self, worker_id, clear_cancel=True):
        self._workers.remove(worker_id, clear_cancel=clear_cancel)

    def _is_worker_canceled(self, worker_id):
        return self._workers.is_canceled(worker_id)

    def _cancel_worker(self, worker_id, worker, progress_dialog, label):
        # Ignore late cancel signals after worker has already completed and been cleaned up.
        if not self._workers.has_active(worker_id):
            return
        self._workers.mark_canceled(worker_id)
        worker.requestInterruption()
        self._log_file_op(label, "CANCELED", "by user")
        progress_dialog.close()
        # Keep canceled marker until late signals are consumed.
        self._cleanup_worker(worker_id, clear_cancel=False)

    def _log_file_op(self, op, status, detail=""):
        msg = f"{op} {status}"
        if detail:
            msg += f": {detail}"
        self.console.log(msg, "FILE")

    def _engine_available_for_ui(self):
        return ENGINE_AVAILABLE

    def go_to_line(self, line_num):
        """Logika skoku do linii zintegrowana z lx_engine i konsolą."""
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return
        if getattr(editor, "large_file_mode", False):
            if hasattr(editor, "jump_to_large_line") and editor.jump_to_large_line(line_num):
                self.console.log(
                    self._tr(
                        "file_navigation_jump_large_view",
                        "Navigation: Jumped to line {line_num} in Large Viewer Mode",
                    ).format(line_num=line_num),
                    "SUCCESS",
                )
            else:
                self.console.log(
                    self._tr("file_navigation_out_of_range", "Navigation: Line {line_num} is out of range").format(
                        line_num=line_num
                    ),
                    "WARN",
                )
            return

        offset = self._find_line_offset_qt(editor, line_num)
        if offset == -1 and ENGINE_AVAILABLE and hasattr(lx_engine, "get_line_offset"):
            content = self._get_editor_text(editor)
            offset = lx_engine.get_line_offset(content, line_num)

        if offset != -1:
            cursor = editor.textCursor()
            cursor.setPosition(offset)
            editor.setTextCursor(cursor)
            editor.ensureCursorVisible()
            
            self.console.log(
                self._tr("file_navigation_jump", "Navigation: Jumped to line {line_num} (offset: {offset})").format(
                    line_num=line_num, offset=offset
                ),
                "SUCCESS",
            )
        else:
            self.console.log(
                self._tr("file_navigation_out_of_range", "Navigation: Line {line_num} is out of range").format(
                    line_num=line_num
                ),
                "WARN",
            )

    def load_current_full_editable(self):
        """Convert current large-viewer tab to full editable document on demand."""
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return False
        if not getattr(editor, "large_file_mode", False):
            self.console.log(self._tr("file_full_editable_already", "Current tab is already fully editable."), "INFO")
            return False

        full_text = self._get_editor_text(editor)
        if len(full_text) > 2_000_000:
            answer = QMessageBox.question(
                self.main_window,
                self._tr("file_safe_edit_confirm_title", "Safe Edit Warning"),
                self._tr(
                    "file_safe_edit_confirm_body",
                    "This file is very large and full editing may reduce responsiveness.\n\nContinue with Safe Edit Mode?",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.console.log(
                    self._tr("file_safe_edit_canceled", "Load Full Editable canceled by user."),
                    "INFO",
                )
                return False
        if hasattr(editor, "disable_large_file_mode"):
            editor.disable_large_file_mode()
        editor.setReadOnly(False)
        editor.setPlainText(full_text)
        if hasattr(editor, "enable_safe_edit_mode") and len(full_text) > 1_000_000:
            editor.enable_safe_edit_mode(snapshot_text=full_text)
        if len(full_text) > 50000 and ENGINE_AVAILABLE and hasattr(editor, "set_turbo_mode"):
            editor.set_turbo_mode(True)
        editor.document().setModified(False)
        self.main_window.editor_manager.handle_text_changed(editor)
        edit_menu = getattr(self.main_window, "edit_menu", None)
        if edit_menu and hasattr(edit_menu, "update_menu_states"):
            edit_menu.update_menu_states()
        self.console.log(
            self._tr("file_full_editable_loaded", "Loaded full editable document (Large Viewer disabled)."),
            "ENGINE",
        )
        return True

    def quick_revert_safe_edit(self):
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor or not hasattr(editor, "quick_revert_safe_edit"):
            return False
        if editor.quick_revert_safe_edit():
            self.main_window.editor_manager.handle_text_changed(editor)
            status_bar = getattr(self.main_window, "custom_status_bar", None)
            if status_bar and hasattr(status_bar, "update_info"):
                status_bar.update_info()
            edit_menu = getattr(self.main_window, "edit_menu", None)
            if edit_menu and hasattr(edit_menu, "update_menu_states"):
                edit_menu.update_menu_states()
            return True
        self.console.log(
            self._tr("file_safe_revert_unavailable", "Safe revert is unavailable for this tab."),
            "INFO",
        )
        return False

    def open_file_by_path(self, path):
        if not os.path.exists(path):
            self._log_file_op("OPEN", "ERROR", f"not found {path}")
            return False

        existing_id, _existing = self._find_active_worker("open", path)
        if existing_id:
            self._log_file_op("OPEN", "SKIPPED", f"already in progress {path}")
            return False

        worker, worker_id = self._open_flow.new_worker(path, progress_dialog=None)
        
        def on_finished(content):
            if self._is_worker_canceled(worker_id):
                self._cleanup_worker(worker_id)
                return
            self._open_flow.finalize(path, content, worker, worker_id, from_restore=True)

        def on_error(err):
            if self._is_worker_canceled(worker_id):
                self._cleanup_worker(worker_id)
                return
            self._handle_error(err)
            self._cleanup_worker(worker_id)

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.start()
        return True

    def open_file(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self.main_window, "Open File", "", "Text Files (*.txt);;All Files (*)"
            )
            if not path: return

        self._log_file_op("OPEN", "START", path)
        existing_id, _existing = self._find_active_worker("open", path)
        if existing_id:
            self._log_file_op("OPEN", "SKIPPED", f"already in progress {path}")
            return
        progress_dialog = self._show_progress(
            self._tr("file_progress_loading", "Loading: {filename}...").format(filename=os.path.basename(path))
        )
        
        worker, worker_id = self._open_flow.new_worker(path, progress_dialog=progress_dialog)
        
        def on_finished(content):
            if self._is_worker_canceled(worker_id):
                progress_dialog.close()
                self._cleanup_worker(worker_id)
                return
            self._open_flow.finalize(path, content, worker, worker_id, from_restore=False)
            progress_dialog.close()
            encoding_label = str(getattr(worker, "used_encoding", "utf-8")).upper()
            self.main_window.statusBar().showMessage(
                self._tr("file_status_opened", "Opened: {path} ({encoding})").format(
                    path=path, encoding=encoding_label
                ),
                3000,
            )

        def on_error(err):
            if self._is_worker_canceled(worker_id):
                progress_dialog.close()
                self._cleanup_worker(worker_id)
                return
            self._handle_error(err)

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.error.connect(progress_dialog.close)
        worker.error.connect(lambda _err: self._cleanup_worker(worker_id))
        worker.start()

    def save_file(self):
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return False

        return self._save_editor(editor)

    def save_file_as(self):
        editor = self.main_window.editor_manager.get_current_editor()
        if not editor:
            return False

        return self._save_editor_as(editor)

    def save_all(self):
        tab_widget = getattr(self.main_window.editor_manager, "tab_widget", None)
        if not tab_widget:
            return False

        modified_targets = []
        for idx in range(tab_widget.count()):
            try:
                editor = tab_widget.widget(idx)
            except Exception:
                editor = None
            if not editor:
                continue

            document = self._get_editor_document(editor)
            is_modified = bool(document.isModified()) if document and hasattr(document, "isModified") else False
            if is_modified:
                modified_targets.append((idx, editor))

        if not modified_targets:
            self._log_file_op("SAVE ALL", "SKIPPED", "no modified tabs")
            return False

        self._log_file_op("SAVE ALL", "START", f"{len(modified_targets)} modified tab(s)")
        started_any = False
        current_index = -1
        if hasattr(tab_widget, "currentIndex"):
            try:
                current_index = int(tab_widget.currentIndex())
            except Exception:
                current_index = -1

        try:
            for _idx, editor in modified_targets:
                started_any = bool(self._save_editor(editor, batch_mode=True)) or started_any
        finally:
            if current_index != -1 and hasattr(tab_widget, "setCurrentIndex"):
                try:
                    tab_widget.setCurrentIndex(current_index)
                except Exception:
                    pass

        if started_any:
            self._log_file_op("SAVE ALL", "SUCCESS", f"{len(modified_targets)} tab(s) queued")
        return started_any

    def _save_editor(self, editor, batch_mode=False):
        if not editor:
            return False

        path = getattr(editor, "file_path", None)
        if not path:
            return self._save_editor_as(editor, batch_mode=batch_mode)

        save_policy = getattr(self.main_window, "config", {}).get("save_encoding_policy", "preserve")
        return self._async_save(
            path,
            self._get_editor_text(editor),
            editor,
            save_encoding=self._resolve_save_encoding(editor, save_policy=save_policy),
            show_progress=not batch_mode,
        )

    def _save_editor_as(self, editor, batch_mode=False):
        tab_widget = getattr(self.main_window.editor_manager, "tab_widget", None)
        previous_index = None
        target_index = -1
        if tab_widget is not None and hasattr(tab_widget, "indexOf"):
            try:
                target_index = int(tab_widget.indexOf(editor))
            except Exception:
                target_index = -1
        if tab_widget is not None and hasattr(tab_widget, "currentIndex"):
            try:
                previous_index = int(tab_widget.currentIndex())
            except Exception:
                previous_index = None
        if tab_widget is not None and target_index != -1 and hasattr(tab_widget, "setCurrentIndex"):
            try:
                tab_widget.setCurrentIndex(target_index)
            except Exception:
                pass

        try:
            # Używamy instancji dialogu zamiast statycznego helpera, żeby mieć stabilne
            # zachowanie confirm-overwrite między środowiskami.
            dialog = QFileDialog(self.main_window, "Save File As")
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setFileMode(QFileDialog.FileMode.AnyFile)
            dialog.setNameFilters(["Text Files (*.txt)", "All Files (*)"])
            dialog.setDefaultSuffix("txt")
            dialog.setOption(QFileDialog.Option.DontConfirmOverwrite, False)

            current_path = getattr(editor, "file_path", None)
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
                    self.console.log(
                        self._tr("file_save_as_canceled_existing", "Save As canceled for existing file: {path}").format(
                            path=path
                        ),
                        "INFO",
                    )
                    return False

            save_policy = getattr(self.main_window, "config", {}).get("save_encoding_policy", "preserve")
            return self._async_save(
                path,
                self._get_editor_text(editor),
                editor,
                is_as=True,
                save_encoding=self._resolve_save_encoding(editor, save_policy=save_policy),
                show_progress=not batch_mode,
            )
        finally:
            if previous_index is not None and tab_widget is not None and hasattr(tab_widget, "setCurrentIndex"):
                try:
                    tab_widget.setCurrentIndex(previous_index)
                except Exception:
                    pass

    def _async_save(self, path, content, editor, is_as=False, save_encoding="utf-8", show_progress=True):
        self._log_file_op("SAVE", "START", path)
        existing_id, _existing = self._find_active_worker("save", path)
        if existing_id:
            self._log_file_op("SAVE", "SKIPPED", f"already in progress {path}")
            return False
        progress_dialog = None
        if show_progress:
            progress_dialog = self._show_progress(
                self._tr("file_progress_saving", "Saving: {filename}...").format(filename=os.path.basename(path))
            )
        
        worker = FileWorker('save', path, content)
        worker.save_encoding = str(save_encoding or "utf-8")
        worker_id = self._register_worker(worker, "save", path)
        
        if progress_dialog is not None:
            worker.progress.connect(progress_dialog.setValue)
        worker.log_signal.connect(self.console.log)
        if progress_dialog is not None:
            progress_dialog.canceled.connect(
                lambda: self._cancel_worker(worker_id, worker, progress_dialog, "Save")
            )

        def on_done(saved_path):
            if self._is_worker_canceled(worker_id):
                if progress_dialog is not None:
                    progress_dialog.close()
                self._cleanup_worker(worker_id)
                return
            saved_encoding = str(getattr(worker, "used_encoding", save_encoding) or "utf-8")
            self._save_flow.finalize(
                editor,
                path,
                saved_path,
                is_as=is_as,
                saved_encoding=saved_encoding,
            )
            if progress_dialog is not None:
                progress_dialog.close()
            self._cleanup_worker(worker_id)

        def on_error(err):
            if self._is_worker_canceled(worker_id):
                if progress_dialog is not None:
                    progress_dialog.close()
                self._cleanup_worker(worker_id)
                return
            self._handle_error(err)

        worker.finished.connect(on_done)
        worker.error.connect(on_error)
        if progress_dialog is not None:
            worker.error.connect(progress_dialog.close)
        worker.error.connect(lambda _err: self._cleanup_worker(worker_id))
        worker.start()
        return True

    def _handle_error(self, err):
        self.console.log(
            self._tr("file_operation_failed", "Operation failed: {error}").format(error=err),
            "ERROR",
        )
        QMessageBox.critical(self.main_window, self._tr("dialog_error_title", "Error"), err)

    def autosave_all(self):
        em = self.main_window.editor_manager
        if self._autosave_worker and self._autosave_worker.isRunning():
            self.console.log(
                self._tr("file_autosave_skip_running", "Autosave skipped: previous cycle is still running."),
                "DEBUG",
            )
            return

        jobs = []
        for idx in range(em.tab_widget.count()):
            try:
                editor = em.tab_widget.widget(idx)
                path = getattr(editor, 'file_path', None)
                if not path:
                    continue

                if getattr(editor, "large_file_mode", False):
                    continue

                document = editor.document() if hasattr(editor, "document") else None
                if document and hasattr(document, "isModified") and not document.isModified():
                    continue

                autosave_path = f"{path}.autosave"
                jobs.append((idx, autosave_path, self._get_editor_text(editor)))
            except Exception as e:
                self.console.log(
                    self._tr("file_autosave_failed_tab", "Autosave failed for tab {idx}: {error}").format(
                        idx=idx, error=str(e)
                    ),
                    "WARN",
                )

        if not jobs:
            return

        self._autosave_worker = AutosaveWorker(jobs)
        self._autosave_worker.completed.connect(self._on_autosave_done)
        self._autosave_worker.finished.connect(self._clear_autosave_worker)
        self._autosave_worker.start()

    def _on_autosave_done(self, count, errors):
        for idx, error in errors:
            self.console.log(
                self._tr("file_autosave_failed_tab", "Autosave failed for tab {idx}: {error}").format(
                    idx=idx, error=error
                ),
                "WARN",
            )

        if count > 0:
            self.console.log(
                self._tr("file_autosaved_count", "Autosaved {count} file(s).").format(count=count),
                "SYSTEM",
            )

    def _clear_autosave_worker(self):
        self._autosave_worker = None
