import json
import os
from PyQt6.QtCore import QLocale
from core.logging import log_message

class LanguageHandler:
    def __init__(self, parent=None, config_lang="system"):
        self.parent = parent
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.lang_dir = os.path.join(self.base_dir, "assets", "languages")
        
        self.current_data = {}
        
        # LOGIKA WYBORU:
        if config_lang == "system":
            target_lang = self.get_system_language()
        else:
            target_lang = config_lang

        # Próba załadowania wybranego języka, jeśli zawiedzie -> wymuś angielski
        if not self.load_language(target_lang):
            print(f"Warning: Could not load {target_lang}, falling back to en-us")
            log_message("WARN", f"Could not load {target_lang}, falling back to en-us", "core.editor.language_handler")
            self.load_language("en-us")

    def get_system_language(self):
        """Sprawdza język systemu i dopasowuje do obsługiwanych plików."""
        # Pobiera np. 'pl_PL' lub 'en_US'
        sys_locale = QLocale.system().name().lower().replace('_', '-') 
        available = self.get_available_languages()

        # 1. Szukamy idealnego dopasowania (np. pl-pl == pl-pl)
        if sys_locale in available:
            return sys_locale
        
        # 2. Szukamy po samym początku (np. 'pl' pasuje do 'pl-pl')
        short_code = sys_locale.split('-')[0]
        for lang in available:
            if lang.startswith(short_code):
                return lang
        
        # 3. Jeśli nic nie pasuje -> angielski
        return "en-us"

    def load_language(self, lang_code):
        """Ładuje plik JSON dla danego kodu języka."""
        file_path = os.path.join(self.lang_dir, f"{lang_code.lower()}.json")
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.current_data = json.load(f)
                self.current_lang = lang_code # Zapisujemy aktualnie używany kod
                return True
            except Exception as e:
                print(f"Error loading language file: {e}")
                log_message("ERROR", f"Error loading language file: {e}", "core.editor.language_handler")
                return False
        return False

    def get_available_languages(self):
        """Skanuje folder languages i zwraca listę dostępnych kodów."""
        if not os.path.exists(self.lang_dir):
            return ["en-us"]
        
        langs = [f.replace('.json', '') for f in os.listdir(self.lang_dir) if f.endswith('.json')]
        return sorted(langs)

    def tr(self, key):
        """Zwraca przetłumaczony tekst."""
        return self.current_data.get(key, key)
