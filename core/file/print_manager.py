from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from PyQt6.QtWidgets import QMessageBox

class PrintManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def print_editor(self, editor):
        """Drukuje zawartość QTextEdit z obsługą tłumaczeń."""
        tr = self.main_window.lang_handler.tr
        
        if editor is None:
            QMessageBox.warning(
                self.main_window, 
                tr("action_print"), # Tytuł okna: "Drukuj"
                tr("error_no_active_editor") # Komunikat: "Brak aktywnego edytora do druku"
            )
            return

        printer = QPrinter()
        dialog = QPrintDialog(printer, self.main_window)
        
        # Okno QPrintDialog zostanie przetłumaczone przez QTranslator w main.py
        if dialog.exec():
            try:
                editor.print(printer)
            except Exception as e:
                QMessageBox.critical(
                    self.main_window, 
                    tr("error_print_failed_title"), 
                    f"{tr('error_print_failed_msg')}\n{e}"
                )