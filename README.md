# detect-law

Zero-shot AI-text detection that runs on your own computer. THE DETECT LAW v8.1, an exact 32-bit integer
sequential decision law over three per-token signals from two small open models (surprise, contrast and
repetition), returns `ai`, `no_evidence` or `undecided`. It flags at most 1% of human texts by design, allowing
for each writer's own steady style; measured, it flagged 0.22% of 3,200 held-out human RAID texts. It stops
reading as soon as the evidence is decisive.

**Official RAID result, v8.1** (672,000-text test set, scored by RAID's evaluation bot on 2026-10-08,
[liamdugan/raid#216](https://github.com/liamdugan/raid/pull/216), official mode; joins the
[RAID leaderboard](https://raid-bench.xyz/leaderboard) when merged):

| RAID test | v7 | **v8.1** |
|---|---|---|
| No attacks, 5% false positives | 80.08% | **92.33%** |
| No attacks, 1% false positives | 68.92% | **86.54%** |
| All texts incl. 11 attacks, 5% false positives | 77.00% | **88.99%** |
| All texts incl. 11 attacks, 1% false positives | 63.87% | **81.37%** |
| AUROC, all texts (no attacks) | 89.86 (90.56) | **96.48 (97.61)** |

The highest score among zero-shot detectors on RAID: Binoculars has 78.98% / 69.54% without attacks. v8.1 is ahead of
Binoculars in all 8 domains and on 9 of the 10 attacks both were scored on. Trained classifiers score higher (up to
99.98%); v8.1 ranks 27th of 44 detectors on all texts. Its weakest attacks are paraphrase (76.57%) and synonyms (80.83%).

A 49-second launch film is in [docs/media/detect-law-v81.mp4](docs/media/detect-law-v81.mp4).

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

Paste text or drop .txt, .md, .docx or .pdf files (several at once gives a list of verdicts). Nothing leaves your computer.

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
| `no_evidence` | Every signal ruled out an AI-sized effect for the generators covered | Nothing. Not proof of human authorship. |
| `undecided` | No significant AI evidence, but not ruled out either. Most human texts end here (98% in tests) | Nothing. Draw no conclusion. |

Each result also carries `score` (√(law_score/256), the number submitted to RAID) and the z of each signal:
`surprise_z`, `contrast_z`, `repetition_z` (about 0 for human text; positive means AI-like).

## Modes

| Mode | Model B | Human texts flagged `ai` | AI texts flagged `ai` |
|---|---|---|---|
| `careful` (default) | Llama-3.2-1B-Instruct, 4-bit | 0.22% | 78.9% |
| `official` | Llama-3.2-1B-Instruct, full precision: the setup submitted to RAID | 0.22% | 80.8% |

Measured on 3,200 held-out human and 1,360 AI RAID texts (8 domains, 34 generator settings, no attacks). Each mode
has its own measured constants. Poetry is the hardest genre (1.25% flagged); no human text over 600 tokens was
flagged. Pick a mode with `--official` (CLI), `"mode": "official"`
(API and MCP), the switch in the web app, or `DETECT_LAW_MODE`.

Choose the backend with `DETECT_LAW_BACKEND=mlx|torch` and the PyTorch device with `DETECT_LAW_DEVICE` (e.g. `cuda:1`).

## Speed and cost (measured)

| Hardware | Per 1,000 words |
|---|---|
| NVIDIA A30, batched (the official RAID run: 672,000 texts in 5.6 h) | 0.14 s |
| NVIDIA T4, batched | 0.6 s |
| Apple M4 Pro (MLX) | 1.7 s |

v8.1 runs both models over every token it reads (v7 ran model B only when needed), so it is slower per word than
v7. 3 billion words take about 115 hours of one A30, roughly $115 if rented. On your own machine it is free.

**Parity:** on 120 RAID texts the package (MLX, this repository's engine) gave the same verdict as the official A30
run every time, with score correlation 0.99992.

## What is inside

| Path | What |
|---|---|
| `src/detectlaw/law/detect_v81.c` | The law: about 325 lines of int32 C, byte-identical to the file used for the official RAID run (sha256 `602d14fd…`). Both modes' constants are generated into it. |
| `src/detectlaw/law/api_v81.c` | Thin interface: feeds a window to the law and reports each signal's z. Changes no decision. |
| `src/detectlaw/engine.py` | Streams text through the law in 200-token windows. MLX and PyTorch backends. |
| `src/detectlaw/server.py`, `web/index.html` | Web app and HTTP API |
| `src/detectlaw/mcp_server.py` | MCP server |
| `src/detectlaw/cli.py`, `files.py` | Command line; .txt/.md/.docx/.pdf reading |
| `tests/smoke_v81.c` | Extreme and random streams in both modes under `-Werror`, UBSan and ASan (`make test`) |
| `archive/v7/` | THE DETECT LAW v7, its proof harness (`make test-v7`) and model card, behind the official v7 result |

## License

Code license not chosen yet; until one is added, all rights are reserved. The models are used
under the Llama 3.2 Community License (see [NOTICE](NOTICE)).
