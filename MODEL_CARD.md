# Model card: detect-law v0.2.0 (THE DETECT LAW v7)

## What it is

An exact 32-bit integer decision rule over two signals computed by two open 1.24B-parameter models
(Meta Llama 3.2: `Llama-3.2-1B` base and `Llama-3.2-1B-Instruct`):

- **Surprise:** how much more predictable each word is than model A expects. Cooler or truncated sampling makes text "cheaper".
- **Contrast:** how much more the chat-tuned model B likes each chosen word than A does, centred for the measured human bias. This signal ignores domain vocabulary.

Early stopping uses Ville's inequality with a Bennett correction (anytime-valid). An end-of-text z-test handles short texts.
"No evidence" requires both signals to rule out an AI-sized effect; anything else is `undecided`.

## Intended use

First-pass triage of long-form text (essays, articles, submissions) in front of **human review**.
Not for automatic penalties, grading or accusations. A verdict is statistical evidence, not proof.

## Modes

| Mode | Model B | Use it for |
|---|---|---|
| `careful` (default) | Llama-3.2-1B-Instruct, 4-bit (`mlx-community/Llama-3.2-1B-Instruct-4bit`; unpacked exactly on PyTorch) | Checking people's work. The law's contrast term was calibrated on this model. |
| `official` | Llama-3.2-1B-Instruct, full precision (`unsloth/Llama-3.2-1B-Instruct`) | Reproducing the RAID score. |

## Official benchmark: RAID

RAID test set, 672,000 texts (11 generators, 8 domains, 4 sampling settings, 11 attacks), scored by RAID's
evaluation bot on 2026-10-06 and listed on the [RAID leaderboard](https://raid-bench.xyz/leaderboard), in official mode.
Metric: share of AI texts caught at a fixed false-positive rate, thresholds set per domain from human texts.

| | 5% FPR | 1% FPR | AUROC |
|---|---|---|---|
| No attacks | 80.08% | 68.92% | 90.56 |
| All texts incl. attacks | 77.00% | 63.87% | 89.86 |
| Binoculars (official), no attacks | 78.98% | 69.54% | – |

Highest no-attack score at 5% FPR among the zero-shot detectors on the leaderboard; Binoculars leads at 1% FPR.
Overall rank 34 of 43. Ahead of Binoculars on 9 of the 10 attacks both were scored on.

## The app's own verdicts on RAID texts

RAID's metric tunes a threshold per domain; the app instead uses the law's fixed rule. On 2,920 labelled texts from
RAID's training data (1,600 human, 1,320 AI, 8 domains, no attacks):

| Mode | Human texts labelled `ai` | AI texts labelled `ai` | AI texts `undecided` |
|---|---|---|---|
| careful | 9 / 1,600 = 0.56% | 811 / 1,320 = 61.4% | 32.2% |
| official | 27 / 1,600 = 1.69% | 885 / 1,320 = 67.0% | 28.0% |

By genre, careful mode flagged book summaries 2.5% (5/200), reviews 1.0%, Reddit 1.0%, and abstracts, news, poetry,
recipes and Wikipedia 0%. Official mode flagged book summaries 8.0% and reviews 3.0%: the full-precision model has a
different human bias on the contrast signal than the 4-bit model the law was calibrated on.

The measurements below were made with the 4-bit model, i.e. careful mode.

## Measured results (English; all numbers from this project's harness, not an independent benchmark)

**False positives** (human text labelled `ai`; the design bound is ≤ 1%):

| Human text | ~200 tokens | Long streams (to 4,000–20,000 tokens) |
|---|---|---|
| IMDB reviews (1,000) | 0.3% | 0–0.27% |
| GitHub issues (80) | 0% | 0% |
| Pre-LLM medical abstracts (200) | 0% | 0.4% |
**With 3% human-style typos** (swap, drop, double or neighbouring-key letter in 3% of words):

| Human text | Clean, ~200 tokens | Typos, ~200 tokens (95% upper bound) | Clean, long streams | Typos, long streams (95% upper bound) |
|---|---|---|---|---|
| IMDB reviews | 3/1000 | 4/1000 (1.02%) | 2/2000 | 0/2000 (0.18%) |
| GitHub issues | 0/80 | 0/80 (4.5%) | 0/2000 | 0/2000 (0.18%) |
| Medical abstracts | 0/200 | 0/200 (1.8%) | 6/2000 | 0/2000 (0.18%) |

Typos add surprise, which pushes text toward the human side, so they do not raise false positives.

**Detection at ~200 tokens:** Llama-3.2-3B chat 100%, Qwen2.5-7B chat 84% (reviews) / 93% (medical), SmolLM2 92%,
Llama base model with top-p 0.9 45%, **Claude 10% (reviews) / 0% (medical abstracts) / 5 of 10 (assistant-style answers)**.

**Long documents:** 100% for every generator tested, including Claude (median 776 tokens for reviews, about 2,000 for medical abstracts).

**Attacks** (documents of ~1,000–1,300 tokens; paraphraser Qwen2.5-7B kept 47–69% of the words):

| | Clean | Typos 3% | Light paraphrase | Paraphrase + typos |
|---|---|---|---|---|
| Claude reviews | 4/4 | 3/4 | 4/4 | 4/4 |
| Claude chat answers | 2/2 | 2/2 | 2/2 | 2/2 |
| Claude medical abstracts | 1/4 | 0/4 | 1/4 | 1/4 |
| Qwen-7B / Llama-3B chat | 10/10 | 10/10 | 10/10 | 10/10 |
| Human reviews | 0/10 | 0/10 | 8/10 | 9/10 |
| Human medical | 0/5 | 0/5 | 2/5 | 2/5 |

**Code-level proofs** (`make test`): exact integer helper; 0 precision violations against the real-number rule in
3,975,668 comparisons; no overflow on 2^20-token worst-case streams; clean under UBSan and ASan.

**Cost:** 0.2–3.6 s per document on an Apple M4 Pro laptop. The law itself costs 0.00014 ms per token; the model passes
cost 0.61 ms (A) and 0.56 ms (B) per token, and B runs only while needed.

## Limits

- **Frontier models in short texts:** Claude-class text is mostly `undecided` below ~800–2,000 tokens.
- **AI-polished human work is flagged:** human text rewritten by an AI paraphraser (more than half its words changed) is detected as AI. The filter sees AI wording, not the origin of the ideas.
- **Narrow testing:** English only; calibrated on reviews, GitHub issues and medical abstracts. Other genres need a human baseline.
- **Accuracy ceiling:** trained classifiers score higher on RAID (up to 99.98% at 5% FPR). Weakest RAID attacks: paraphrase 68.3%, synonyms 71.7%.
- **Platform:** Apple Silicon (MLX) and PyTorch (NVIDIA GPU or CPU). The two backends agree to within 0.04 in z on tested texts, with identical verdicts.
