import sys
import os
import glob

# 1. Absolutne minimum na start - ścieżki
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path: 
    sys.path.insert(0, current_dir)

SETUP_COMMANDS = {
    "build",
    "build_ext",
    "build_py",
    "install",
    "develop",
    "sdist",
    "bdist",
    "bdist_wheel",
    "egg_info",
    "clean",
}

SETUP_FLAGS = {
    "--help",
    "--help-commands",
    "--name",
    "--version",
}


def run_setup():
    from setuptools import setup
    from pybind11.setup_helpers import Pybind11Extension, build_ext

    engine_sources = sorted(glob.glob(os.path.join("core", "cengines", "**", "*.cpp"), recursive=True))
    if not engine_sources:
        raise RuntimeError("No C++ engine sources found in core/cengines")

    ext_modules = [
        Pybind11Extension(
            "lx_engine",
            engine_sources,
            cxx_std=17,
            extra_compile_args=["-O3"],
        ),
    ]

    setup(
        name="lx_engine",
        version="1.5",
        author="Nefiu",
        description="C++ Core for LxNotes",
        ext_modules=ext_modules,
        cmdclass={"build_ext": build_ext},
        zip_safe=False,
    )


def is_setup_invocation(argv):
    if len(argv) <= 1:
        return False

    for arg in argv[1:]:
        if arg in SETUP_COMMANDS or arg in SETUP_FLAGS:
            return True
        if arg.startswith("bdist_"):
            return True
    return False


def run_app():
    from core.logging import setup_runtime_logging, log_message
    setup_runtime_logging(current_dir)

    # 2. Importy niezbędne tylko do Splasha (szybkie)
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtCore import Qt, QPropertyAnimation

    class LxSplashScreen(QWidget):
        def __init__(self, is_wayland=False):
            super().__init__()
            # Usunięcie flag, które mogą opóźniać renderowanie na niektórych DE
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            
            layout = QVBoxLayout()
            self.setLayout(layout)

            self.logo_label = QLabel()
            icon_path = os.path.join(current_dir, "assets", "icons", "splash.png")
            if os.path.exists(icon_path):
                self.logo_label.setPixmap(QPixmap(icon_path).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.logo_label.setText("🐧")
            
            self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.logo_label)

            self.msg_label = QLabel("LxNotes: Initializing...")
            self.msg_label.setStyleSheet("color: white; background: rgba(25,25,25,230); padding: 15px; border-radius: 10px; font-family: sans-serif;")
            self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.msg_label)

            # Ręczne centrowanie bez czekania na QApplication.primaryScreen() jeśli to możliwe
            self.adjustSize()
            self.center_on_screen()
            
            self.fade_anim = None
            if not is_wayland:
                self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
                self.fade_anim.setDuration(500)
                self.fade_anim.setStartValue(1.0)
                self.fade_anim.setEndValue(0.0)
                self.fade_anim.finished.connect(self.close)

        def center_on_screen(self):
            screen = QApplication.primaryScreen().availableGeometry()
            self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

        def update_msg(self, text):
            self.msg_label.setText(text)
            QApplication.processEvents() # Wymusza przerysowanie GUI

        def fade_out_and_close(self):
            if self.fade_anim: self.fade_anim.start()
            else: self.close()

    # --- KROK 1: NATYCHMIASTOWY START GUI ---
    app = QApplication(sys.argv)
    app.setApplicationName("LxNotes")
    
    # Odpalamy splash zanim zaimportujemy ciężkie moduły
    splash = LxSplashScreen() 
    splash.show()
    splash.update_msg("Engine is starting...") 

    # --- KROK 2: CIĘŻKIE IMPORTY I MANAGER ---
    # Importujemy to dopiero TUTAJ, żeby nie blokować startu Splasha
    from core.theme.platform_manager import PlatformManager
    import importlib.util

    platform_mgr = PlatformManager()
    boot_logs = []

    def log_boot(msg):
        print(msg)
        log_message("BOOT", msg, "boot")
        boot_logs.append(msg)
        splash.update_msg(msg)

    # Konfiguracja środowiska (RTLD_GLOBAL itd.)
    platform_mgr.setup_runtime_environment(log_boot)
    
    # Poprawiamy splash o info o Waylandzie (teraz już wiemy czy jest)
    is_wayland = platform_mgr.is_wayland()
    if is_wayland and splash.fade_anim:
        splash.fade_anim = None 

    # --- KROK 3: KOMPILACJA SILNIKA ---
    builder_path = os.path.join(current_dir, "core", "editor", "builder.py")
    if os.path.exists(builder_path):
        try:
            log_boot("Checking Engine components...")
            spec = importlib.util.spec_from_file_location("builder_module", builder_path)
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            build_result = builder.run_build()
            if build_result is True:
                log_boot("✅ Engine build: SUCCESS")
            elif build_result == getattr(builder, "UP_TO_DATE", "UP_TO_DATE"):
                log_boot("ℹ️ Engine build: up to date")
            else:
                log_boot(f"⚠️ Engine build skipped/failed: {build_result}")
        except Exception as e:
            log_boot(f"❌ Builder Error: {e}")

    # --- KROK 4: URUCHOMIENIE OKNA GŁÓWNEGO ---
    try:
        log_boot("Launching UI...")
        from ui.main_window.main_window import MainWindow
        
        window = MainWindow(startup_logs=boot_logs, platform_manager=platform_mgr)
        platform_mgr.set_app_id()
        
        window.show()
        splash.fade_out_and_close()
        sys.exit(app.exec())
        
    except Exception as e:
        log_boot(f"🛑 Critical Startup Error: {e}")
        if 'splash' in locals(): splash.close()

if __name__ == "__main__":
    if is_setup_invocation(sys.argv):
        run_setup()
    else:
        run_app()
