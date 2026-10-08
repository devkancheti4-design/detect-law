"""Compile the C law (law/api_v81.c around law/detect_v81.c) into one shared library per mode, on first use."""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "law", "api_v81.c")
DEPS = [SRC, os.path.join(HERE, "law", "detect_v81.c")]
MODE_ID = {"careful": 0, "official": 1}


def _compile(lib, mode_id):
    cc = os.environ.get("CC", "cc")
    os.makedirs(os.path.dirname(lib), exist_ok=True)
    try:
        subprocess.run([cc, "-O2", "-Wall", "-Wextra", "-Werror", "-std=c99", f"-DV81_MODE={mode_id}",
                        "-shared", "-fPIC", "-o", lib, SRC], check=True)
    except FileNotFoundError:
        sys.exit("detect-law needs a C compiler to build its law once. On macOS run: xcode-select --install; "
                 "on Debian/Ubuntu: sudo apt install build-essential; or set CC to your compiler.")


def library_path(mode="careful"):
    m = MODE_ID[mode]
    name = f"liblaw_v81_m{m}" + (".dylib" if sys.platform == "darwin" else ".so")
    newest = max(os.path.getmtime(p) for p in DEPS)
    for d in (os.path.join(HERE, "law"), os.path.expanduser("~/.cache/detect-law")):   # package dir, else user cache
        lib = os.path.join(d, name)
        if os.path.exists(lib) and os.path.getmtime(lib) >= newest:
            return lib
        try:
            _compile(lib, m)
            return lib
        except (OSError, subprocess.CalledProcessError):
            continue
    sys.exit("detect-law could not compile its law (law/api_v81.c); check that your C compiler works.")
