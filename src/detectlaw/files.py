"""Read text out of .txt / .md / .docx / .pdf files on any platform."""
import os, re, shutil, subprocess, zipfile
from xml.etree import ElementTree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx(path):
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    paras = []
    for p in root.iter(W + "p"):
        paras.append("".join(t.text or "" for t in p.iter(W + "t")))
    return "\n".join(paras)


def _pdf(path):
    try:
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-enc", "UTF-8", path, "-"], capture_output=True, text=True, check=True).stdout
    raise ValueError("reading PDFs needs either `pip install pypdf` or the pdftotext tool")


def read_text(path):
    """Plain text of a document. Raises ValueError for formats it cannot read."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return _docx(path)
    if ext == ".pdf":
        return _pdf(path)
    if ext in (".doc", ".rtf", ".pages", ".odt"):
        if shutil.which("textutil"):                         # macOS
            return subprocess.run(["textutil", "-convert", "txt", "-stdout", path], capture_output=True, text=True, check=True).stdout
        raise ValueError(f"save {os.path.basename(path)} as .docx, .pdf or .txt first")
    with open(path, "rb") as f:
        raw = f.read()
    if b"\x00" in raw[:4096]:
        raise ValueError(f"{os.path.basename(path)} looks like a binary file, not text")
    return re.sub(r"\r\n?", "\n", raw.decode("utf-8", errors="replace"))
