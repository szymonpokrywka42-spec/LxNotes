import sys
import os
import glob

# 1. Absolutne minimum na start - ścieżki
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path: 
    sys.path.insert(0, current_dir)
lxbinman_local = os.path.join(current_dir, "LxBinMan")
if os.path.isdir(lxbinman_local) and lxbinman_local not in sys.path:
    sys.path.insert(0, lxbinman_local)

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
        version="1.6",
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
    from core.bootstrap.app_bootstrap import run_app as _run_app

    _run_app(current_dir)

if __name__ == "__main__":
    if is_setup_invocation(sys.argv):
        run_setup()
    else:
        run_app()
