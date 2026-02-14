import os
import sys
import platform
import ctypes
import subprocess

class PlatformManager:
    def __init__(self):
        self.os_type = platform.system()
        self.de = self._detect_de()
        self.session = os.environ.get('XDG_SESSION_TYPE', 'unknown').lower()
        self.logger = None  # Tu podepniemy console_logic z MainWindow
        
        # Rozszerzony słownik cech środowisk Linuxowych
        self.de_features = {
            "GNOME":     {"csd": True,  "tray": False, "wm": "Mutter"},
            "KDE":       {"csd": False, "tray": True,  "wm": "KWin"},
            "XFCE":      {"csd": False, "tray": True,  "wm": "Xfwm4"},
            "CINNAMON":  {"csd": False, "tray": True,  "wm": "Muffin"},
            "PANTHEON":  {"csd": True,  "tray": False, "wm": "Gala"},
            "MATE":      {"csd": False, "tray": True,  "wm": "Marco"},
            "LXQT":      {"csd": False, "tray": True,  "wm": "Openbox/KWin"},
            "DEEPIN":    {"csd": True,  "tray": True,  "wm": "DeepinWM"},
            "BUDGIE":    {"csd": True,  "tray": True,  "wm": "BudgieWM"},
            "I3":        {"csd": False, "tray": True,  "wm": "i3wm"},
            "SWAY":      {"csd": False, "tray": True,  "wm": "Sway"}
        }

    def _detect_de(self):
        """Precyzyjna detekcja środowiska graficznego."""
        de_raw = os.environ.get('XDG_CURRENT_DESKTOP', '').upper()
        
        if ':' in de_raw:
            de_raw = de_raw.split(':')[-1]
            
        if not de_raw:
            de_raw = os.environ.get('DESKTOP_SESSION', 'UNKNOWN').upper()

        # Mapowanie na standardowe klucze
        mapping = {
            "GNOME": "GNOME", "UNITY": "GNOME",
            "KDE": "KDE", "PLASMA": "KDE",
            "XFCE": "XFCE",
            "MINT": "CINNAMON", "CINNAMON": "CINNAMON",
            "PANTHEON": "PANTHEON", "ELEMENTARY": "PANTHEON",
            "MATE": "MATE",
            "LXQT": "LXQT",
            "DEEPIN": "DEEPIN",
            "BUDGIE": "BUDGIE",
            "I3": "I3",
            "SWAY": "SWAY"
        }

        for key, value in mapping.items():
            if key in de_raw:
                return value
        
        return de_raw if de_raw else "GENERIC_LINUX"

    def log(self, message, level="SYSTEM"):
        """Bezpieczne wysyłanie logów do konsoli UI lub terminala."""
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    def setup_runtime_environment(self, boot_log_func=None):
        """Inicjalizuje środowisko przed startem QApplication."""
        # Używamy przekazanej funkcji logującej (dla splash screena) lub printa
        def internal_log(m):
            if boot_log_func: boot_log_func(m)
            else: self.log(m)

        internal_log(f"🌐 Platform: {self.os_type} | Session: {self.session}")

        if self.os_type == "Linux":
            # Optymalizacja symboli dla silnika C++
            try:
                sys.setdlopenflags(sys.getdlopenflags() | ctypes.RTLD_GLOBAL)
                internal_log("⚙️ RTLD_GLOBAL enabled (C++ symbols optimization).")
            except Exception as e:
                internal_log(f"⚠️ RTLD_GLOBAL fail: {e}")

            # Wybór backendu Qt
            if self.session == "wayland":
                os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
                if self.de in ["GNOME", "PANTHEON"]:
                    os.environ["QT_WAYLAND_DISABLE_WINDOWDECORATION"] = "1"
            else:
                os.environ["QT_QPA_PLATFORM"] = "xcb"

            # Poprawki renderowania dla GTK
            if self.de in ["GNOME", "XFCE", "MATE", "CINNAMON"]:
                os.environ["QT_STYLE_OVERRIDE"] = "gtk2"
                internal_log("🎨 GTK Hinting enabled.")

        internal_log(f"🖥️ Detected DE: {self.de}")

    def apply_platform_tweaks(self, main_window):
        """Aplikuje poprawki wizualne do gotowego okna i podłącza logger."""
        # Podpinamy system logowania MainWindow do managera
        if hasattr(main_window, 'console_logic'):
            self.logger = main_window.console_logic
            self.log(f"Manager connected to UI Console. DE: {self.de}", "SUCCESS")

        features = self.de_features.get(self.de, {"csd": False, "tray": True})
        
        # Specyficzne dla KDE (Blur/Transparent)
        if self.de == "KDE":
            try:
                main_window.setAttribute(ctypes.c_bool(True).value, "WA_TranslucentBackground")
                self.log("✨ KDE Translucency applied.")
            except: pass

        # Specyficzne dla GNOME/Pantheon (Modern look)
        if features.get("csd"):
            main_window.setProperty("linux_style", "modern")
            self.log("🖼️ Applying Modern CSD layout.")

    def set_app_id(self):
        """Ustawia nazwę procesu dla Task Managera (Linux)."""
        if self.os_type == "Linux":
            try:
                lib = ctypes.CDLL(None)
                lib.g_set_prgname(b"lxnotes")
                if hasattr(lib, 'g_set_application_name'):
                    lib.g_set_application_name(b"LxNotes")
            except: pass

    def get_info(self):
        return f"{self.os_type} {self.de} ({self.session})"

    def is_wayland(self):
        return self.session == "wayland"