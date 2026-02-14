import os
import shlex
import sys
import subprocess 
import time
import glob
from datetime import datetime
import sysconfig

# --- KONFIGURACJA ŚCIEŻEK ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Zakładamy: project_root/core/editor/builder.py -> wychodzimy 2 poziomy w górę do project_root
BASE_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))

# Silnik jest teraz modułowy: kompilujemy wszystkie .cpp z core/cengines/
ENGINE_DIR = os.path.join(BASE_DIR, "core", "cengines")

try:
    SUFFIX = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
except Exception:
    SUFFIX = ".so"

# Plik wynikowy w głównym katalogu: project_root/lx_engine.so
OUTPUT_LIB = os.path.join(BASE_DIR, f"lx_engine{SUFFIX}")
COMPILER = "g++"

try:
    PYBIND_FLAGS = shlex.split(
        subprocess.check_output([sys.executable, "-m", "pybind11", "--includes"], text=True).strip()
    )
except Exception:
    PYBIND_FLAGS = ["-I/usr/include/python3.13", "-I/usr/include/pybind11"]

FLAGS = ["-O3", "-shared", "-std=c++17", "-fPIC", *PYBIND_FLAGS]
UP_TO_DATE = "UP_TO_DATE"


def get_source_files():
    return sorted(glob.glob(os.path.join(ENGINE_DIR, "**", "*.cpp"), recursive=True))


def get_latest_source_mtime():
    files = get_source_files()
    if not files:
        return 0
    return max(os.path.getmtime(path) for path in files if os.path.exists(path))


def is_build_required():
    """Sprawdza czy biblioteka wymaga przebudowania."""
    if not get_source_files():
        return False
    if not os.path.exists(OUTPUT_LIB):
        return True
    return get_latest_source_mtime() > os.path.getmtime(OUTPUT_LIB)

def run_build():
    timestamp = datetime.now().strftime('%H:%M:%S')
    
    source_files = get_source_files()
    if not source_files:
        return f"[{timestamp}] ❌ Nie znaleziono plików źródłowych .cpp w: {ENGINE_DIR}"

    if not is_build_required():
        return UP_TO_DATE

    # Kompilacja
    output_tmp = f"{OUTPUT_LIB}.tmp"
    command = [COMPILER, *FLAGS, *source_files, "-o", output_tmp]
    result = subprocess.run(command, capture_output=True, text=True)
    
    if result.returncode == 0:
        try:
            os.replace(output_tmp, OUTPUT_LIB)
            return True
        except OSError as e:
            return f"[{timestamp}] ⚠️ Nie udało się podmienić biblioteki: {e}"
    else:
        if os.path.exists(output_tmp):
            try:
                os.remove(output_tmp)
            except OSError:
                pass
        return result.stderr

def build_with_logs():
    ts = datetime.now().strftime('%H:%M:%S')
    res = run_build()
    if res == UP_TO_DATE:
        print(f"[{ts}] ℹ️  Engine bez zmian, pomijam kompilację.")
        return True
    if res is True:
        print(f"[{ts}] 🛠️  Kompilacja {len(get_source_files())} plików C++ -> {os.path.basename(OUTPUT_LIB)}")
        print(f"[{ts}] ✅ Sukces!")
        return True
    else:
        print(f"[{ts}] ❌ Błąd kompilacji:\n{res}")
        return False

if __name__ == "__main__":
    if not get_source_files():
        print(f"❌ Krytyczny błąd: Brak plików źródłowych .cpp w {ENGINE_DIR}")
        sys.exit(1)

    last_mtime = get_latest_source_mtime()
    build_with_logs()
    
    print(f"👀 Watcher działa. Śledzę zmiany w {ENGINE_DIR}...")
    try:
        while True:
            if get_source_files():
                mtime = get_latest_source_mtime()
                if mtime > last_mtime and build_with_logs():
                    last_mtime = mtime
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Zatrzymano.")
