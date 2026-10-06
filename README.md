# detect-law

Zero-shot AI-text detection that runs on your own computer. An exact 32-bit integer decision law
over two small open models returns `ai`, `no_evidence` or `undecided`, flags at most 1% of human
texts by design (measured: 0.56% of 1,600 human RAID texts in careful mode), and stops reading as soon
as the evidence is decisive.

**Official RAID result** (672,000-text test set, scored by RAID's evaluation bot on 2026-10-06,
[submission #212](https://github.com/liamdugan/raid/pull/212), official mode): **80.08%** of AI text caught at
5% false positives without attacks, ahead of Binoculars (78.98%), the best zero-shot score on the
[RAID leaderboard](https://raid-bench.xyz/leaderboard) (rank 34 of 43 overall). 77.00% on all texts including 11 adversarial attacks. Binoculars leads at 1% false positives
(69.54% vs 68.92%), and trained classifiers score higher (up to 99.98%).

**Read [MODEL_CARD.md](MODEL_CARD.md) before using it on real people's work.** The verdict is
evidence, not proof.

## Install

```bash
pip install "git+https://github.com/devkancheti4-design/detect-law"
```

Python 3.10+ and a C compiler (the law compiles itself on first use). Apple Silicon runs on the GPU with
MLX; Windows, Linux and Intel Macs use PyTorch (NVIDIA GPU if present, otherwise CPU). On first run the two
models download once from Hugging Face: `unsloth/Llama-3.2-1B` plus `mlx-community/Llama-3.2-1B-Instruct-4bit`
(careful mode) and, if you use official mode, `unsloth/Llama-3.2-1B-Instruct`. After that it works offline.

## Use

**Web app**

```bash
detect-law-server            # then open http://127.0.0.1:8765
```

Paste text or drop a .txt, .md, .docx or .pdf file. Nothing leaves your computer.

**Command line**

```bash
detect-law essay.docx report.pdf          # one line per file
detect-law notes.txt --json               # full result
```

**HTTP API** (served by `detect-law-server`; interactive docs at `/docs`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/detect` | `{"text": "..."}` → verdict + evidence |
| POST | `/v1/detect-file?name=essay.docx` | raw file bytes as the body |
| GET | `/v1/health` | version, models, backend |
| GET | `/v1/info` | measured results and known limits |

Set `DETECT_API_KEY` to require the header `X-API-Key`.

**MCP server** (Claude and other assistants; the check still runs locally)

```bash
claude mcp add detect-law -- uvx --from git+https://github.com/devkancheti4-design/detect-law detect-law-mcp
```

Other clients:

```json
{ "mcpServers": { "detect-law": { "command": "uvx", "args": ["--from", "git+https://github.com/devkancheti4-design/detect-law", "detect-law-mcp"] } } }
```

Tools: `check_text`, `check_file` (absolute path to .txt/.md/.docx/.pdf), `about_detect_law`.

**Python**

```python
from detectlaw import Engine
r = Engine().detect(open("essay.txt").read())
print(r["verdict"], r["evidence"])
```

| Verdict | Meaning | What to do |
|---|---|---|
| `ai` | Statistical evidence of AI generation | Human review. Never automatic penalties. |
| `no_evidence` | An AI-sized effect was ruled out for the generators covered | Nothing. Not proof of human authorship. |
| `undecided` | Not enough evidence, usually a short text | Nothing. |

## Modes

| Mode | Model B | Human texts flagged `ai` | AI texts flagged `ai` |
|---|---|---|---|
| `careful` (default) | Llama-3.2-1B-Instruct, 4-bit: the model the law was calibrated on | 0.56% | 61.4% |
| `official` | Llama-3.2-1B-Instruct, full precision: the setup scored on RAID | 1.69% | 67.0% |

Measured on 2,920 labelled RAID texts (1,600 human, 1,320 AI, 8 domains). Book summaries are the hardest genre:
2.5% flagged in careful mode, 8.0% in official mode. Pick a mode with `--official` (CLI), `"mode": "official"`
(API and MCP), the switch in the web app, or `DETECT_LAW_MODE`.

Choose the backend with `DETECT_LAW_BACKEND=mlx|torch` and the PyTorch device with `DETECT_LAW_DEVICE` (e.g. `cuda:1`).

## Speed and cost (measured)

| Hardware | Per 1,000 words |
|---|---|
| NVIDIA A40 | 0.10 s |
| Apple M4 Pro (MLX) | 1.4 s |
| CPU only, 4 cores | 3.0 s |

3 billion words take about 84 hours of one A40, roughly $40 if rented. On your own machine it is free.

## What is inside

| Path | What |
|---|---|
| `src/detectlaw/law/detect_v7.c` | The law: about 150 lines of int32 C. Its header holds the full derivation. |
| `src/detectlaw/engine.py` | Streams text through the law; runs model B only while the law asks for it. MLX and PyTorch backends. |
| `src/detectlaw/server.py`, `web/index.html` | Web app and HTTP API |
| `src/detectlaw/mcp_server.py` | MCP server |
| `src/detectlaw/cli.py`, `files.py` | Command line; .txt/.md/.docx/.pdf reading |
| `tests/eval_v7.c` | Proof harness: exactness, precision against the real-number rule, overflow, sanitizers (`make test`) |

## License

Code license not chosen yet; until one is added, all rights are reserved. The models are used
under the Llama 3.2 Community License (see [NOTICE](NOTICE)).
