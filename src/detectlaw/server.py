"""Local web app + HTTP API for THE DETECT LAW v8.1.

    detect-law-server                      then open http://127.0.0.1:8765
    curl -s localhost:8765/v1/detect -H 'content-type: application/json' -d '{"text": "..."}'

Optional: set DETECT_API_KEY to require the header  X-API-Key: <key>.
One worker: the models run one request at a time (the engine holds a lock).
"""
import os, tempfile
from typing import Literal
from importlib.resources import files as _pkg
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from . import __version__
from .engine import Engine, LAW_VERSION
from .facts import INFO

MAX_CHARS, MAX_FILE = 300_000, 20 * 1024 * 1024
app = FastAPI(title="Detect Law", version=__version__,
              description="Zero-shot AI-text triage with a bounded false-positive rate. Verdicts are evidence, not proof.")
engine = Engine()
API_KEY = os.environ.get("DETECT_API_KEY")


class DetectRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_CHARS, description="Long-form text (essay, article, paper)")
    strip_references: bool = Field(True, description="Ignore everything from a References/Bibliography heading on")
    prose_only: bool = Field(True, description="Skip headings, table cells and equation fragments")
    mode: Literal["careful", "official"] = Field("careful", description="careful: fewer human texts flagged; "
                                                 "official: the exact setup submitted to the RAID benchmark")


def _auth(key):
    if API_KEY and key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home():
    return _pkg("detectlaw").joinpath("web/index.html").read_text(encoding="utf-8")


@app.post("/v1/detect")
def detect(req: DetectRequest, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    return engine.detect(req.text, strip_references=req.strip_references, prose_only=req.prose_only, mode=req.mode)


@app.post("/v1/detect-file")
async def detect_file(request: Request, name: str = Query(..., description="file name, e.g. essay.docx"),
                      mode: Literal["careful", "official"] = Query("careful"),
                      x_api_key: str | None = Header(default=None)):
    """Send the raw file bytes as the request body (.txt, .md, .docx or .pdf)."""
    _auth(x_api_key)
    body = await request.body()
    if not body or len(body) > MAX_FILE:
        raise HTTPException(status_code=413, detail="file is empty or larger than 20 MB")
    from .files import read_text
    ext = os.path.splitext(os.path.basename(name))[1].lower() or ".txt"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(body)
    try:
        text = read_text(f.name)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e).replace(os.path.basename(f.name), os.path.basename(name)))
    finally:
        os.unlink(f.name)
    if not text.strip():
        raise HTTPException(status_code=422, detail="no text found in the file")
    return {"file": os.path.basename(name), **engine.detect(text[:MAX_CHARS], mode=mode)}


@app.get("/v1/health")
def health():
    return {"status": "ok", "version": __version__, "law": LAW_VERSION, "models": engine.models}


@app.get("/v1/info")
def info():
    """The measured claims and the known limits, so integrators know exactly what they get."""
    return INFO


def run():
    """Entry point: detect-law-server [--host 127.0.0.1] [--port 8765]"""
    import argparse, uvicorn
    p = argparse.ArgumentParser(prog="detect-law-server")
    p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    print(f"Detect Law is running: open http://{a.host}:{a.port}", flush=True)
    uvicorn.run(app, host=a.host, port=a.port, workers=1)
