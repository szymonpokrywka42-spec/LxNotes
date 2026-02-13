# LxNotes

**LxNotes** is a lightweight Linux notepad with tabbed documents, dark/light themes, and customizable fonts – fast, simple, and user-friendly, perfect for managing multiple text files in one window.
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
* Windows 11-inspired theme refresh for dark/light palettes.
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
pip install PyQt6 chardet
And you just need to turn on main.py file
with vscode or terminal or .desktop file 
and application will turn on.
