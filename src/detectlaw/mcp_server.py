"""MCP server: lets Claude and other AI assistants check text with THE DETECT LAW, locally.

    detect-law-mcp                         (stdio; add it to your MCP client, see README)

Tools: check_text, check_file, about_detect_law. Everything runs on this machine; no text leaves it.
The models load in the background at start-up, so the first check only waits for what is left.
"""
import os, sys, threading

try:                                                    # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:                                     # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
    from mcp.server.fastmcp.exceptions import ToolError

from .facts import INFO

_engine, _error, _ready = None, None, threading.Event()


def _load():
    global _engine, _error
    try:
        from .engine import Engine
        _engine = Engine()
    except Exception as e:                              # reported on the first tool call
        _error = e
    finally:
        _ready.set()


def _get():
    _ready.wait()
    if _error is not None:
        raise ToolError(f"detect-law could not load its models: {_error}")
    return _engine


HOW_TO_READ = ("ai = statistical evidence of AI generation (some human texts get it too): send to human review, "
               "never use as proof. no_evidence = an AI-sized effect was ruled out, not proof of human authorship. "
               "undecided = too little text to say; draw no conclusion.")

server = _Server(
    "detect-law",
    instructions="Zero-shot AI-text detector that runs locally. Use check_text for pasted text and check_file for a "
                 "document on disk. Report the verdict with its meaning; never present it as proof of authorship. "
                 "Short texts (under ~200 words) are often undecided; longer texts give stronger evidence.",
)


@server.tool()
def check_text(text: str, mode: str = "careful", strip_references: bool = True) -> dict:
    """Check whether a piece of English prose (an essay, article, review, answer) shows statistical evidence of
    being written by an AI model. Returns verdict (ai | no_evidence | undecided), what it means, and the evidence.
    Works best on 200+ words. mode: "careful" (default, fewer human texts flagged) or "official" (the exact setup
    scored on the RAID benchmark). Set strip_references=False to also read a reference list."""
    if not text or not text.strip():
        raise ToolError("text is empty: pass the text to check")
    if mode not in ("careful", "official"):
        raise ToolError('mode must be "careful" or "official"')
    r = _get().detect(text, strip_references=strip_references, mode=mode)
    return {**r, "how_to_read": HOW_TO_READ}


@server.tool()
def check_file(path: str, mode: str = "careful", strip_references: bool = True) -> dict:
    """Check a document on this computer (.txt, .md, .docx or .pdf) for statistical evidence of AI-written text.
    Give an absolute path. mode: "careful" (default) or "official". Returns the same verdict and evidence as check_text."""
    if mode not in ("careful", "official"):
        raise ToolError('mode must be "careful" or "official"')
    from .files import read_text
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        raise ToolError(f"no such file: {path} (give an absolute path)")
    try:
        text = read_text(path)
    except (OSError, ValueError) as e:
        raise ToolError(str(e))
    if not text.strip():
        raise ToolError(f"no text found in {path}")
    r = _get().detect(text, strip_references=strip_references, mode=mode)
    return {"file": path, **r, "how_to_read": HOW_TO_READ}


@server.tool()
def about_detect_law() -> dict:
    """How the detector works, its official RAID benchmark results, speed, cost and known limits."""
    return INFO


def main():
    threading.Thread(target=_load, daemon=True).start()
    server.run("stdio")


if __name__ == "__main__":
    main()
