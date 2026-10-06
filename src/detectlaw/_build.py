"""Compile the C law (law/detect_v7.c) into a shared library on first use."""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "law", "detect_v7.c")


def _compile(lib):
    cc = os.environ.get("CC", "cc")
    os.makedirs(os.path.dirname(lib), exist_ok=True)
    try:
        subprocess.run([cc, "-O2", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC", "-o", lib, SRC], check=True)
    except FileNotFoundError:
        sys.exit("detect-law needs a C compiler to build its law once. On macOS run: xcode-select --install; "
                 "on Debian/Ubuntu: sudo apt install build-essential; or set CC to your compiler.")


def library_path():
    name = "liblaw_v7" + (".dylib" if sys.platform == "darwin" else ".so")
    for d in (os.path.join(HERE, "law"), os.path.expanduser("~/.cache/detect-law")):   # package dir, else user cache
        lib = os.path.join(d, name)
        if os.path.exists(lib) and os.path.getmtime(lib) >= os.path.getmtime(SRC):
            return lib
        try:
            _compile(lib)
            return lib
        except (OSError, subprocess.CalledProcessError):
            continue
    sys.exit("detect-law could not compile its law (law/detect_v7.c); check that your C compiler works.")
