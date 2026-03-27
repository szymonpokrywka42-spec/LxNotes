import glob
import os
import shlex
import subprocess
import sys
import sysconfig
from pathlib import Path

UP_TO_DATE = "UP_TO_DATE"


def _project_root() -> Path:
    # core/editor/engine_build_task.py -> project root
    return Path(__file__).resolve().parents[2]


def _source_files(base_dir: Path) -> list[str]:
    pattern = str(base_dir / "core" / "cengines" / "**" / "*.cpp")
    return sorted(glob.glob(pattern, recursive=True))


def _latest_mtime(paths: list[str]) -> float:
    if not paths:
        return 0.0
    return max(os.path.getmtime(p) for p in paths if os.path.exists(p))


def _get_ext_suffix() -> str:
    try:
        return sysconfig.get_config_var("EXT_SUFFIX") or ".so"
    except Exception:
        return ".so"


def _pybind_flags() -> list[str]:
    cmd = [sys.executable, "-m", "pybind11", "--includes"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "pybind11 --includes failed").strip())
    return shlex.split(result.stdout.strip())


def run_build() -> str:
    base_dir = _project_root()
    sources = _source_files(base_dir)
    if not sources:
        return "FAILED: no .cpp sources in core/cengines"

    out_lib = base_dir / f"lx_engine{_get_ext_suffix()}"
    src_latest = _latest_mtime(sources)
    if out_lib.exists() and out_lib.stat().st_mtime >= src_latest:
        return UP_TO_DATE

    flags = ["-O3", "-shared", "-std=c++17", "-fPIC", *_pybind_flags()]
    tmp_out = Path(str(out_lib) + ".tmp")
    cmd = ["g++", *flags, *sources, "-o", str(tmp_out)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        try:
            tmp_out.unlink(missing_ok=True)
        except Exception:
            pass
        err = (result.stderr or result.stdout or "build failed").strip()
        return f"FAILED: {err}"

    os.replace(tmp_out, out_lib)
    return "SUCCESS"


def main() -> int:
    status = run_build()
    print(f"__LX_ENGINE_BUILD_STATUS__={status}")
    return 0 if status in (UP_TO_DATE, "SUCCESS") else 1


if __name__ == "__main__":
    exit_code = main()
    # VSCode/Pylance debuggers often break on SystemExit, which is noisy when
    # running this helper directly from IDE. Keep exit codes for normal CLI runs.
    if sys.gettrace() is None:
        raise SystemExit(exit_code)
