from typing import List, Optional

from PyQt6.QtWidgets import QTabWidget, QMessageBox
from PyQt6.QtCore import Qt
from core.editor.editor_tab import EditorTab

class EditorManager:
    def __init__(self, parent):
        self.parent = parent  # Referencja do MainWindow
        self.console = parent.console_logic 
        
        self.tab_widget = QTabWidget()
        self._closed_tabs_history: List[dict] = []
        self._closed_tabs_limit = 20
        # V1.2: Ustawienia dla nowoczesnego wyglądu kart
        self.tab_widget.setTabsClosable(False) # Włączone iksy na kartach
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True) 
        self.tab_widget.setUsesScrollButtons(False)

        tab_bar = self.tab_widget.tabBar()
        if tab_bar is not None:
            tab_bar.setDrawBase(False)
            tab_bar.setExpanding(False)
            tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        self.console.log("Initializing EditorManager with Evergreen UI...", "SYSTEM")
        self.new_tab()

    def new_tab(self, *args, title="Untitled"):
        """Tworzy nową kartę z edytorem."""
        if not isinstance(title, str):
            title = "Untitled"

        editor = EditorTab(console=self.console)
        editor.textChanged.connect(lambda: self.handle_text_changed(editor))

        index = self.tab_widget.addTab(editor, title)
        self.tab_widget.setCurrentIndex(index)
        
        self.console.log(f"New tab created: '{title}'", "EDITOR")
        return editor

    def handle_text_changed(self, editor: EditorTab):
        """Aktualizuje tytuł karty (dodaje/usuwa gwiazdkę)."""
        index = self.tab_widget.indexOf(editor)
        if index == -1: return
        
        title = self.tab_widget.tabText(index)
        is_modified = editor.document().isModified()
        
        if is_modified and not title.endswith("*"):
            self.tab_widget.setTabText(index, title + "*")
        elif not is_modified and title.endswith("*"):
            self.tab_widget.setTabText(index, title[:-1])

    def close_tab(self, index: int):
        """Zamyka pojedynczą kartę."""
        if index == -1: return

        editor = self.tab_widget.widget(index)
        if isinstance(editor, EditorTab) and editor.document().isModified():
            # Przełączamy na tę kartę, żeby użytkownik widział co zamyka
            self.tab_widget.setCurrentIndex(index)
            if not self.prompt_save_changes(editor):
                return 

        if isinstance(editor, EditorTab):
            self._remember_closed_tab(editor, self.tab_widget.tabText(index))
            if getattr(editor, "large_file_mode", False) and hasattr(editor, "disable_large_file_mode"):
                editor.disable_large_file_mode()

        self.tab_widget.removeTab(index)
        if self.tab_widget.count() == 0:
            self.new_tab()

    def _remember_closed_tab(self, editor: EditorTab, title: str):
        snapshot = {
            "title": title.replace("*", "").strip() or "Untitled",
            "content": editor.get_full_text() if hasattr(editor, "get_full_text") else editor.toPlainText(),
            "file_path": getattr(editor, "file_path", None),
            "is_turbo_mode": bool(getattr(editor, "is_turbo_mode", False)),
            "file_encoding": getattr(editor, "file_encoding", "utf-8"),
            "file_encoding_confidence": float(getattr(editor, "file_encoding_confidence", 0.0) or 0.0),
            "safe_edit_mode": bool(getattr(editor, "safe_edit_mode", False)),
        }
        self._closed_tabs_history.append(snapshot)
        if len(self._closed_tabs_history) > self._closed_tabs_limit:
            self._closed_tabs_history = self._closed_tabs_history[-self._closed_tabs_limit :]

    def reopen_last_closed_tab(self) -> bool:
        if not self._closed_tabs_history:
            return False

        snapshot = self._closed_tabs_history.pop()
        editor = self.new_tab(title=snapshot.get("title", "Untitled"))
        restored_content = snapshot.get("content", "")
        if isinstance(restored_content, str) and len(restored_content) > 8_000_000 and hasattr(editor, "enable_large_file_mode"):
            editor.enable_large_file_mode(restored_content)
        else:
            editor.setPlainText(restored_content)
        editor.file_path = snapshot.get("file_path")
        editor.file_encoding = snapshot.get("file_encoding", "utf-8")
        editor.file_encoding_confidence = float(snapshot.get("file_encoding_confidence", 0.0) or 0.0)
        if snapshot.get("is_turbo_mode") and hasattr(editor, "set_turbo_mode"):
            editor.set_turbo_mode(True)
        if snapshot.get("safe_edit_mode") and hasattr(editor, "enable_safe_edit_mode"):
            editor.enable_safe_edit_mode(snapshot_text=restored_content)
        editor.document().setModified(False)
        self.handle_text_changed(editor)
        return True

    def check_all_unsaved(self) -> bool:
        """
        Sprawdza wszystkie karty przed zamknięciem aplikacji.
        Wyświetla jeden zbiorczy dialog, jeśli są niezapisane zmiany.
        """
        unsaved_editors: List[EditorTab] = []
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, EditorTab) and widget.document().isModified():
                unsaved_editors.append(widget)

        if not unsaved_editors:
            return True

        tr = self.parent.lang_handler.tr
        
        msg = QMessageBox(self.parent)
        msg.setWindowTitle(tr("msg_unsaved_title"))
        msg.setText(tr("msg_unsaved_text"))
        msg.setIcon(QMessageBox.Icon.Warning)
        
        # Używamy Twoich nowych kluczy tłumaczeń
        save_all_btn = msg.addButton(tr("btn_save_all"), QMessageBox.ButtonRole.AcceptRole)
        discard_btn = msg.addButton(tr("btn_discard"), QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = msg.addButton(tr("btn_cancel"), QMessageBox.ButtonRole.RejectRole)
        
        msg.setDefaultButton(save_all_btn)
        msg.exec()
        
        clicked = msg.clickedButton()
        
        if clicked == save_all_btn:
            # Tutaj logika zapisu wszystkich (pętla po unsaved_editors)
            return self.save_all_sequence(unsaved_editors)
        elif clicked == discard_btn:
            return True # Zamykamy wszystko bez zapisywania
        else:
            return False # Anulujemy zamykanie aplikacji

    def prompt_save_changes(self, editor: EditorTab) -> bool:
        """Dialog pytający o zapis zmian dla POJEDYNCZEJ karty."""
        tr = self.parent.lang_handler.tr
        index = self.tab_widget.indexOf(editor)
        file_name = self.tab_widget.tabText(index).replace("*", "")
        
        msg = QMessageBox(self.parent)
        msg.setWindowTitle(tr("msg_unsaved_title"))
        # Dynamiczne wstawienie nazwy pliku do tłumaczenia, jeśli masz taką obsługę, 
        # lub proste złożenie tekstu:
        msg.setText(f"{tr('msg_unsaved_text_single')} '{file_name}'?") 
        
        save_btn = msg.addButton(tr("btn_save"), QMessageBox.ButtonRole.AcceptRole)
        discard_btn = msg.addButton(tr("btn_discard"), QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = msg.addButton(tr("btn_cancel"), QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        clicked = msg.clickedButton()
        
        if clicked == save_btn:
            # Wywołujemy zapis przez MainWindow -> FileHandler
            return self.parent.file_handler.save_file()
        elif clicked == discard_btn:
            return True
        return False

    def save_all_sequence(self, editors: List[EditorTab]) -> bool:
        """Pomocnicza metoda do zapisu listy edytorów."""
        for editor in editors:
            index = self.tab_widget.indexOf(editor)
            self.tab_widget.setCurrentIndex(index)
            if not self.parent.file_handler.save_file():
                return False # Jeśli użytkownik anuluje zapis któregokolwiek pliku, przerywamy
        return True

    def get_all_editors(self) -> List[EditorTab]:
        editors: List[EditorTab] = []
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, EditorTab):
                editors.append(widget)
        return editors

    def get_current_editor(self) -> Optional[EditorTab]:
        widget = self.tab_widget.currentWidget()
        return widget if isinstance(widget, EditorTab) else None
