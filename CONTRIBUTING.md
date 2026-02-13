# Contributing to LxNotes 🚀

First of all, thank you! LxNotes is growing
fast, and we’re thrilled to have you here. This document will help you understand how the project is structured and how you can contribute effectively.

## 🏗 Project Architecture

LxNotes follows a modular structure to keep the code clean and maintainable.

### 🎨 Frontend (The Face)
- **Framework:** PyQt6.
- **Main Window:** Located in `main_window.py`. It handles the main UI assembly.
- **Styling:** We use CSS-like stylesheets (QSS) to manage themes.
- **Components:** Custom widgets (like the Editor or Console) are organized into separate modules to keep `MainWindow` lightweight.

### ⚙️ Backend & Logic (The Brain)
- **File Handling:** Managed by `file_handler.py` and `lx_engine.cpp` for simplicity and performance.
- **Performance Engine (C++):** Our secret sauce. For large files, the `lx_engine` module (C++) takes over text processing to ensure "Turbo Mode" performance.
- **Encoding:** We use `chardet` for intelligent file encoding detection.

---

## 🌍 Localization (Adding New Languages)

We want LxNotes to speak every language! Here is how the system works:

### 1. The JSON Files
All translations live in the `/languages` directory. To add a new language:
- Copy an existing file (e.g., `en-us.json`).
- Rename it using the standard locale code (e.g., `fr-fr.json` for French).
- Translate the values, but **do not change the keys**.

### 2. Mapping Filenames to Human Names
The app needs to know that `en-us.json` should be displayed as "English" in the UI.
- Locate the **`settings_dialog.py`** class (ui/dialogs/).
- Find the `languages` list (a list of tuples).
- Add your language in this format: `("Human Readable Name", "locale-code")`.
  
**Example:**
```python
languages = [
    ("English", "en-us"),
    ("Polski", "pl-pl"),
    ("Italiano", "it-it") # Add yours here!
]
