import os


class OpenFlow:
    def __init__(self, handler):
        self.handler = handler

    def new_worker(self, path, progress_dialog=None):
        worker = self.handler._worker_factory("open", path)
        worker_id = self.handler._register_worker(worker, "open", path)
        worker.log_signal.connect(self.handler.console.log)
        if progress_dialog is not None:
            worker.progress.connect(progress_dialog.setValue)
            progress_dialog.canceled.connect(
                lambda: self.handler._cancel_worker(worker_id, worker, progress_dialog, "Open")
            )
        return worker, worker_id

    def finalize(self, path, content, worker, worker_id, from_restore=False):
        editor = self.handler.main_window.editor_manager.new_tab(title=os.path.basename(path))
        editor.file_path = path
        editor.file_encoding = getattr(worker, "used_encoding", "utf-8")
        editor.file_encoding_confidence = float(getattr(worker, "encoding_confidence", 0.0) or 0.0)
        if hasattr(editor, "disable_safe_edit_mode"):
            editor.disable_safe_edit_mode()

        if len(content) > 8_000_000 and hasattr(editor, "enable_large_file_mode"):
            editor.enable_large_file_mode(content)
            if from_restore:
                self.handler.console.log(
                    self.handler._tr(
                        "file_large_viewer_restored_enabled",
                        "Large Viewer Mode enabled for restored session file.",
                    ),
                    "ENGINE",
                )
            else:
                self.handler.console.log(
                    self.handler._tr(
                        "file_large_viewer_ultra_enabled",
                        "Large Viewer Mode enabled for ultra-large file.",
                    ),
                    "ENGINE",
                )
        else:
            editor.setPlainText(content)

        if len(content) > 50000 and self.handler._engine_available_for_ui() and hasattr(editor, "set_turbo_mode"):
            editor.set_turbo_mode(True)
            if not from_restore:
                self.handler.console.log(self.handler._tr("file_turbo_enabled", "Turbo Mode enabled."), "ENGINE")

        editor.document().setModified(False)
        self.handler.main_window.editor_manager.handle_text_changed(editor)
        self.handler.recent_files.add_file(path)
        status_bar = getattr(self.handler.main_window, "custom_status_bar", None)
        if status_bar and hasattr(status_bar, "update_info"):
            status_bar.update_info()

        encoding_label = str(getattr(editor, "file_encoding", "utf-8")).upper()
        self.handler.console.log(
            self.handler._tr("file_detected_encoding", "Detected encoding for {filename}: {encoding}").format(
                filename=os.path.basename(path),
                encoding=encoding_label,
            ),
            "INFO",
        )

        if from_restore:
            self.handler._log_file_op("OPEN", "SUCCESS", f"restored {os.path.basename(path)}")
        else:
            self.handler._log_file_op("OPEN", "SUCCESS", path)
        self.handler._cleanup_worker(worker_id)


class SaveFlow:
    def __init__(self, handler):
        self.handler = handler

    def finalize(self, editor, path, saved_path, is_as=False, saved_encoding="utf-8"):
        final_path = saved_path or path
        normalized_encoding = str(saved_encoding or "utf-8").lower()
        editor.file_path = final_path
        editor.file_encoding = normalized_encoding
        editor.file_encoding_confidence = 1.0
        if is_as:
            idx = self.handler.main_window.editor_manager.tab_widget.indexOf(editor)
            if idx >= 0:
                self.handler.main_window.editor_manager.tab_widget.setTabText(idx, os.path.basename(final_path))

        editor.document().setModified(False)
        self.handler.main_window.editor_manager.handle_text_changed(editor)
        self.handler.recent_files.add_file(final_path)
        self.handler.main_window.statusBar().showMessage(
            self.handler._tr("file_status_saved", "Saved: {path}").format(path=final_path),
            2000,
        )
        self.handler.console.log(
            self.handler._tr(
                "file_saved_encoding_policy",
                "Saved using encoding policy: {filename} (encoding={encoding}, confidence=100.0%)",
            ).format(
                filename=os.path.basename(final_path),
                encoding=normalized_encoding.upper(),
            ),
            "INFO",
        )
        self.handler._log_file_op("SAVE", "SUCCESS", final_path)
