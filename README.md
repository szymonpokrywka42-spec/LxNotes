# LxNotes

**LxNotes** is a lightweight Linux notepad with tabbed documents, dark/light themes, and customizable fonts – fast, simple, and user-friendly, perfect for managing multiple text files in one window.
---

## 🚀 Release v1.6 [Stable]

This release focuses on architecture cleanup, startup decoupling, stronger regression coverage, runtime i18n completion, and safer file-operation behavior under cancellation/race conditions.

### 🧱 Architecture & Refactor
* **Startup bootstrap extracted:** application runtime startup flow was moved from `main.py` into `core/bootstrap/app_bootstrap.py` for a cleaner entrypoint.
* **`FileHandler` modularized:** open/save finalization logic is now delegated to `OpenFlow` and `SaveFlow` in `core/file/operation_flows.py`.
* **Worker lifecycle centralized:** active/canceled worker state moved into `WorkerRegistry` for clearer ownership and safer cleanup.
* **Worker responsibilities split:** file worker logic was separated into `OpenFileWorker` and `SaveFileWorker`, while preserving compatibility via the `FileWorker(...)` factory.

### 🛡 Reliability & Cancel Safety
* **Late-signal cancel guards:** after user cancel, delayed `finished/error` signals are ignored safely to prevent stale UI updates.
* **Consistent cancel path:** interruption and cleanup handling is now explicit and uniform across open/save flows.
* **Duplicate-op protection:** duplicate open/save operations on the same path are blocked with clear logs.

### 🌐 Internationalization (Runtime)
* **Runtime i18n expanded:** console command outputs and file-operation UI/runtime messages now use translation keys with safe fallbacks.
* **Language consistency checks:** all locale files are validated against `en-us` key coverage.
* **Product-term consistency:** `GoToLine`, `Large Viewer`, and `Turbo` tokens are enforced in critical runtime strings across locales.
* **Localization pass completed for key locales:** improved quality and natural phrasing for updated runtime keys across multiple languages.

### 🧪 Testing & Quality
* **Large Viewer regression suite added:** activation state, chunk switching, full-editable conversion, and read-only keypress/hint behavior.
* **Save As overwrite flow tests added:** dialog cancel, overwrite reject (`No`), and overwrite accept (`Yes`) scenarios.
* **Startup smoke test added:** offscreen `MainWindow` construction sanity test.
* **Expanded automated baseline:** regression suite now covers startup, console help, file flows, cancel races, LxCharset bridge, dialogs, language consistency, and Large Viewer behavior.

### 🛠 UX / Behavior Updates
* **Command Palette removed fully:** command palette implementation and related UI hooks were removed as requested.
* **Status and encoding feedback improved:** open flow continues to expose detected encoding and operation state in logs/status area.

### ⚡ Performance & Stability (latest)
* **Throttled fsync logging:** runtime log flushing now batches fsync pressure to reduce I/O spikes while keeping crash diagnostics reliable.
* **Find/Replace path improved:** search/replace flow is more stable on repeated actions and large-buffer scans.
* **Statusbar debounce + cache:** status insights refresh is debounced and cached to avoid unnecessary UI recomputation.
* **Safer recent-files persistence:** recent list writes are guarded to reduce corruption risk on interrupted or rapid session shutdown.

### 🧭 Roadmap Additions (Current Dev Cycle)
* **Save All workflow:** menu + shortcut flow for saving all modified tabs, with safe handling for untitled tabs.
* **Console power commands:** `save-all`, `recent`, and `open-recent <n>` for faster keyboard-driven workflows.
* **C++ search fast-path:** Find Next and Replace All can use native-engine paths with Qt fallback.
* **Quick Open ranking:** lightweight fuzzy-like ranking and result limiting for large history sets.

---

## 🚀 Release v1.5 [Stable]

This release focuses on stability hardening, production-grade diagnostics, and full local charset detection integration.

### 🧱 Reliability Fixes
* **Save/Save As stability:** fixed async save flow and return status handling to avoid inconsistent behavior in save operations.
* **Overwrite flow:** improved `Save As` overwrite handling with explicit confirmation path and safer dialog behavior.
* **Console `logs` crash fix:** replaced platform-unsafe logs-folder opener path to prevent crashes on Linux.

### 📈 Logging & Crash Diagnostics
* **Runtime logger added:** centralized runtime logging layer with file + stderr handlers.
* **Crash visibility:** enabled `faulthandler` crash dumps and unhandled exception hooks (`sys` and `threading`).
* **Safer flush policy:** file logs now use explicit flush + fsync to reduce log loss during crashes.
* **Fallback instrumentation:** modules that previously relied on plain `print` now also report into runtime logging.

### ⚙️ Engine + I/O Follow-up
* Continued engine-side decoding integration in file-open path, with clearer decode metadata in logs.

### 🔤 LxCharset Integration
* **`chardet` removed from app runtime:** file encoding detection no longer depends on external `chardet`.
* **Local module integrated:** `LxCharset` is now bundled in project tree and used by `FileHandler` for preferred-encoding detection.
* **Feedback wired to console/logs:** LxCharset events are forwarded into LxNotes console stream and log files during file-open operations.
* **Fallback kept safe:** existing decode fallback order in open pipeline is preserved to avoid regressions on malformed files.
* **Stable integration contract:** see `docs/LXCHARSET_API.md` for the API surface required by LxNotes.

---
## 🚀 Release v1.4 [Stable]

This release upgrades the native engine architecture and moves file decoding to a new C++ pipeline for better scalability with large and mixed-encoding text files.

### ⚙️ Engine Upgrade (C++)
* **Modular C++ Core:** `lx_engine` has been refactored into dedicated engine modules (`search`, `stats`, `text_utils`, `logger`, `io_codec`).
* **Build System Upgrade:** Engine build now compiles all C++ sources under `core/cengines/**` with C++17.
* **New Native API:** Added `decode_bytes(...)` and `get_line_offsets(...)` in `lx_engine`.

### 🚀 Backend Performance
* **Heavy Decoding Offloaded to C++:** File open pipeline now uses `lx_engine.decode_bytes(...)` in `FileWorker`.
* **Encoding Metadata:** Decode flow now returns selected encoding, fallback usage, and attempted codecs for better diagnostics.
* **Safer Fallback Strategy:** Strict-first decoding and controlled replace fallback for malformed input.

### 🎨 UI/UX Polish
* Windows inspired theme refresh for dark/light palettes.
* Tabbar geometry and edge cleanup for more consistent visual joins.
* Settings combobox arrow rendering hardened with custom paint fallback.

---
## 🚀 Release v1.3 [Stable]

This update marks a major milestone for **LxNotes**, transforming it into a truly global text editor. With the integration of the enhanced C++ engine, LxNotes now supports a wide array of international scripts and advanced navigation features.

### 🌍 New Languages (Total: 15)
The localization "Armageddon" is complete. LxNotes now speaks 8 new languages, covering major global markets and diverse scripts:
* **East Asian:** Japanese (日本語), Chinese (简体中文), Korean (한국어)
* **Southeast Asian:** Vietnamese (Tiếng Việt)
* **Middle Eastern:** Arabic (العربية)
* **European:** Swedish (Svenska), Portuguese (Português), Ukrainian (Українська)

### ⚙️ Backend & Engine Improvements
* **Advanced Font Rendering:** Updated the C++ core engine to handle non-standard fonts, complex ligatures, and multi-byte UTF-8 characters seamlessly.
* **Stability:** Optimized the `FileHandler` bridge to ensure zero-lag performance when switching between different linguistic encodings.

### 🛠 New Features & Options
* **Go To Line (`Ctrl+G`):** A high-performance navigation tool powered by the C++ engine for instant jumping to specific line offsets, even in massive files.
* **Console Integration:** All file operations and engine tasks are now logged in real-time for easier debugging and system monitoring.

---
*Status: Feature Freeze. Moving into Maintenance & Bug-fix mode.*

---
## 1.2

🚀 Version 1.2 – Release Notes

Version 1.2 focuses primarily on a Frontend overhaul and critical Backend stabilization.
🖥️ Frontend

  Visual Redesign: Completely new User Interface with a modern, refined color palette.
  Toolbar Enhancements: Fixed and optimized toolbar options for a smoother workflow.
  UX Improvements: Corrected UI behavior to ensure better responsiveness and intuitive navigation.

⚙️ Backend

  Stability & Bugfixes: General core improvements and logic fixes to eliminate previous issues.
  Language System: Fixed localization and language-handling logic.
  Dev-Friendly Logging: Added a comprehensive logging system to assist developers in debugging.
  Persistent Configuration: Implemented a config system that remembers user-chosen options and settings across sessions.
  Core Refactoring: Optimized internal engine for better performance and reliability.

<img width="1109" height="783" alt="Zrzut ekranu_20260210_134827" src="https://github.com/user-attachments/assets/4891b6d3-d2bb-4cb7-a883-ecad2e55b1ba" />

---
## 1.1

Version 1.1 focuses on system stability, full Linux ecosystem integration, and improved communication between the C++ engine and the user interface.
Main Features
Universal Platform Manager

A new intelligent module PlatformManager has been introduced to automatically adapt LxNotes to the user's environment:

  -DE Detection: Precise identification of GNOME, KDE Plasma, XFCE, Cinnamon, MATE, Pantheon, and more.
  -Wayland Ready: Automatic configuration of the graphics backend and HiDPI scaling fixes for modern Wayland sessions.
  -System Tweaks: Native GTK font rendering for GNOME/XFCE and support for background translucency in KDE Plasma.
  -RTLD_GLOBAL: Optimized C++ symbol loading, ensuring stable interaction between the engine and the Python interpreter.

Enhanced Internationalization (i18n)

  -LanguageHandler: Redesigned translation system supporting dynamic language switching without requiring an application restart.
  -Contextual Translation: Integration of translations across the editor's context menu, dialog windows, and system messages.

New LxStatusBar

A completely new status bar implementation featuring:

  -Engine Status: Visual indicator of the C++ engine connection status (Python vs Native mode).
  -Live Stats: Dynamic tracking of cursor position, file encoding, and real-time text changes.
  -Auto-Retranslate: Full support for real-time language updates.

Startup Optimization

  -Instant Splash Screen: GUI initialization has been moved to the very beginning of the process, resulting in the immediate appearance of the startup logo.
  -Lazy Loading: Heavy modules, including the engine builder, are loaded in the background with progress updates displayed in the Splash window.
  -System Logs (F12): All boot phase events are captured and accessible via the internal developer console.

## 1.0

- Multiple tabs for editing several documents at once  
- Dark and Light themes  
- Font customization: type, size, bold, italic, underline, color  
- Undo/Redo, Cut/Copy/Paste, Select All  
- Open, Save, Save As functionality  
- About dialog with version and credits
- AND MUCH MORE! 

---

## Installation and setup.

1. Make sure you have **Python 3.10+** installed.  
2. Install dependencies:

```bash
pip install PyQt6
```

3. Start the app:

```bash
python3 main.py
```

You can also run it from VS Code or a `.desktop` launcher.

## Developer checks

```bash
./scripts/run_checks.sh
```
