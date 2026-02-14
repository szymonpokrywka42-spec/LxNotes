from PyQt6.QtWidgets import QTabWidget, QMessageBox
from PyQt6.QtCore import Qt
from core.editor.editor_tab import EditorTab

class EditorManager:
    def __init__(self, parent):
        self.parent = parent  # Referencja do MainWindow
        self.console = parent.console_logic 
        
        self.tab_widget = QTabWidget()
        # V1.2: Ustawienia dla nowoczesnego wyglądu kart
        self.tab_widget.setTabsClosable(False) # Włączone iksy na kartach
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True) 
        self.tab_widget.setUsesScrollButtons(False)

        tab_bar = self.tab_widget.tabBar()
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

    def handle_text_changed(self, editor):
        """Aktualizuje tytuł karty (dodaje/usuwa gwiazdkę)."""
        index = self.tab_widget.indexOf(editor)
        if index == -1: return
        
        title = self.tab_widget.tabText(index)
        is_modified = editor.document().isModified()
        
        if is_modified and not title.endswith("*"):
            self.tab_widget.setTabText(index, title + "*")
        elif not is_modified and title.endswith("*"):
            self.tab_widget.setTabText(index, title[:-1])

    def close_tab(self, index):
        """Zamyka pojedynczą kartę."""
        if index == -1: return

        editor = self.tab_widget.widget(index)
        if isinstance(editor, EditorTab) and editor.document().isModified():
            # Przełączamy na tę kartę, żeby użytkownik widział co zamyka
            self.tab_widget.setCurrentIndex(index)
            if not self.prompt_save_changes(editor):
                return 

        self.tab_widget.removeTab(index)
        if self.tab_widget.count() == 0:
            self.new_tab()

    def check_all_unsaved(self):
        """
        Sprawdza wszystkie karty przed zamknięciem aplikacji.
        Wyświetla jeden zbiorczy dialog, jeśli są niezapisane zmiany.
        """
        unsaved_editors = [
            self.tab_widget.widget(i) for i in range(self.tab_widget.count())
            if isinstance(self.tab_widget.widget(i), EditorTab) and self.tab_widget.widget(i).document().isModified()
        ]

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

    def prompt_save_changes(self, editor):
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

    def save_all_sequence(self, editors):
        """Pomocnicza metoda do zapisu listy edytorów."""
        for editor in editors:
            index = self.tab_widget.indexOf(editor)
            self.tab_widget.setCurrentIndex(index)
            if not self.parent.file_handler.save_file():
                return False # Jeśli użytkownik anuluje zapis któregokolwiek pliku, przerywamy
        return True

    def get_all_editors(self):
        return [self.tab_widget.widget(i) for i in range(self.tab_widget.count())]

    def get_current_editor(self):
        widget = self.tab_widget.currentWidget()
        return widget if isinstance(widget, EditorTab) else None
