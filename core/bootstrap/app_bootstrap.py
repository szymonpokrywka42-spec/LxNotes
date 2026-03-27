import os
import re
import sys


def run_app(current_dir):
    from core.logging import setup_runtime_logging, log_message

    setup_runtime_logging(current_dir)

    # 2. Importy niezbędne tylko do Splasha (szybkie)
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
    from PyQt6.QtGui import QPixmap, QIcon
    from PyQt6.QtCore import Qt, QPropertyAnimation

    class LxSplashScreen(QWidget):
        def __init__(self, supports_opacity=True):
            super().__init__()
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)

            self.panel = QWidget()
            self.panel.setObjectName("splashPanel")
            self.panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.panel.setStyleSheet(
                "#splashPanel {"
                "background: rgba(12, 16, 24, 210);"
                "border: 1px solid rgba(86, 102, 124, 0.70);"
                "border-radius: 12px;"
                "}"
            )
            root.addWidget(self.panel)

            layout = QVBoxLayout(self.panel)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(10)

            self.logo_label = QLabel()
            self.logo_label.setStyleSheet("background: transparent; border: none;")
            self.logo_label.setFixedSize(160, 160)
            app_icon_path = os.path.join(current_dir, "assets", "icons", "icon.png")
            if os.path.exists(app_icon_path):
                self.setWindowIcon(QIcon(app_icon_path))
            icon_path = os.path.join(current_dir, "assets", "icons", "splash.png")
            if os.path.exists(icon_path):
                self.logo_label.setPixmap(
                    QPixmap(icon_path).scaled(
                        132,
                        132,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                self.logo_label.setText("🐧")
                self.logo_label.setStyleSheet(
                    "background: transparent; border: none; color: #c9d4e3; font-size: 58px;"
                )

            self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.logo_label)

            self.msg_label = QLabel("LxNotes: Initializing...")
            self.msg_label.setStyleSheet(
                "color: #dce7f3; background: rgba(16,22,32,210); "
                "padding: 10px 12px; border-radius: 8px; "
                "border: 1px solid rgba(100,115,136,0.45); font-family: sans-serif;"
            )
            self.msg_label.setWordWrap(True)
            self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.msg_label)

            self.adjustSize()
            self.center_on_screen()

            self.fade_anim = None
            if supports_opacity:
                self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
                self.fade_anim.setDuration(500)
                self.fade_anim.setStartValue(1.0)
                self.fade_anim.setEndValue(0.0)
                self.fade_anim.finished.connect(self.close)

        def center_on_screen(self):
            primary = QApplication.primaryScreen()
            if primary is None:
                return
            screen = primary.availableGeometry()
            self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

        def update_msg(self, text):
            self.msg_label.setText(text)
            QApplication.processEvents()

        def fade_out_and_close(self):
            if self.fade_anim:
                self.fade_anim.start()
            else:
                self.close()

    # --- KROK 1: NATYCHMIASTOWY START GUI ---
    app = QApplication(sys.argv)
    app.setApplicationName("LxNotes")
    platform_name = (app.platformName() or "").lower()
    supports_opacity = not any(x in platform_name for x in ("wayland", "offscreen", "minimal"))

    splash = LxSplashScreen(supports_opacity=supports_opacity)
    splash.show()
    splash.update_msg("Engine is starting...")

    # --- KROK 2: CIĘŻKIE IMPORTY I MANAGER ---
    from core.theme.platform_manager import PlatformManager

    platform_mgr = PlatformManager()
    boot_logs = []

    def log_boot(msg, level="BOOT"):
        raw = str(msg or "").strip()
        level_norm = str(level or "BOOT").upper()

        matched = re.match(r"^\[([A-Za-z_]+)\]\s*(.*)$", raw)
        if matched:
            detected = matched.group(1).upper()
            rest = matched.group(2).strip()
            if level_norm in {"", "BOOT"}:
                level_norm = detected
            raw = rest

        print(raw)
        log_message(level_norm, raw, "boot")
        boot_logs.append(f"[{level_norm}] {raw}")
        splash.update_msg(raw)

    platform_mgr.setup_runtime_environment(log_boot)

    is_wayland = platform_mgr.is_wayland()
    if is_wayland and splash.fade_anim:
        splash.fade_anim = None

    # --- KROK 3: KOMPILACJA SILNIKA (LxBinMan) ---
    build_task = os.path.join(current_dir, "core", "editor", "engine_build_task.py")
    if os.path.exists(build_task):
        try:
            os.environ.setdefault("LXBINMAN_DISABLE_FATAL", "1")
            from lxbinman import feedback as binman_feedback
            from lxbinman import builder as binman_builder

            def _on_binman_event(event):
                event_level = getattr(event, "level", "INFO")
                event_message = getattr(event, "message", "")
                event_code = getattr(event, "code", "")
                if event_code:
                    log_boot(f"LxBinMan/{event_code}: {event_message}", event_level)
                else:
                    log_boot(f"LxBinMan: {event_message}", event_level)

            binman_feedback.enable_console(False)
            if hasattr(binman_feedback, "set_kill_on_error"):
                binman_feedback.set_kill_on_error(False)
            binman_feedback.subscribe(_on_binman_event)

            log_boot("Checking Engine components...")
            build_result = binman_builder.run_script(
                build_task,
                feedback=binman_feedback,
                cwd=current_dir,
            )
            stdout = str(build_result.get("stdout", "") or "")
            if build_result.get("ok"):
                if "__LX_ENGINE_BUILD_STATUS__=UP_TO_DATE" in stdout:
                    log_boot("ℹ️ Engine build: up to date")
                elif "__LX_ENGINE_BUILD_STATUS__=SUCCESS" in stdout:
                    log_boot("✅ Engine build: SUCCESS")
                else:
                    log_boot("ℹ️ Engine build: completed")
            else:
                err = str(build_result.get("stderr", "") or "").strip()
                log_boot(f"⚠️ Engine build skipped/failed: {err or 'unknown error'}")
            binman_feedback.unsubscribe(_on_binman_event)
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
        if "splash" in locals():
            splash.close()
