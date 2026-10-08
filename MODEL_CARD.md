# Model card: detect-law v0.3.0 (THE DETECT LAW v8.1)

## What it is

An exact 32-bit integer sequential decision law (`src/detectlaw/law/detect_v81.c`) over three per-token signals from
two open 1.24B-parameter models (Meta Llama 3.2: `Llama-3.2-1B` base as A, `Llama-3.2-1B-Instruct` as B):

- **Surprise:** how much more predictable each token is than A expects (clip(L − E, ±8 bits), weighted by A's variance).
- **Contrast:** how much more B likes each chosen token than A does (clip(D − K, ±6 bits)). Domain vocabulary cancels out.
- **Repetition (new in v8.1):** whether the token was already used in the window, against the probability A put on
  already-used tokens (x = q − R). AI sampling with a repetition penalty repeats less than A predicts.

**The null allows for style.** Each human text may carry its own persistent bias (spread κ across texts), so the
variance of each arm is ρ·W + κ²·W² rather than ρ·W; a distinctive human voice stops looking like ever-growing
evidence. The end-of-text test uses that heterogeneity z. The anytime-valid early-stop lines (Ville's inequality)
spend part of their share on the bias, so each line's slope carries c + κ·z(α_b).

**Error budget:** 1% in total across the three arms (surprise 0.45%, contrast 0.40%, repetition 0.15%), each split
between the end test, the bias charge and the martingale lines (80/10/10). **Verdicts:** `ai` as soon as any arm
crosses its line, or at the end test; `no_evidence` only if every arm rules out an AI-sized effect; otherwise
`undecided`. **Score:** law_score = Σ max(z, 0)², evidence toward AI only; the package reports √(law_score/256).

The constants are measured on human text only (no training on AI text): per arm, the mean c, the within-text
variance ratio ρ and the between-text spread κ, on 3,200 human RAID training texts (400 per domain).

| Arm | c (pooled) | ρ | κ |
|---|---|---|---|
| Surprise | +0.00953 | 0.811 | 0.01402 |
| Contrast, careful mode | +0.05293 | 1.000 | 0.04038 |
| Contrast, official mode | +0.06516 | 1.000 | 0.04408 |
| Repetition | −0.07434 | 1.013 | 0.12042 |

The generator accepted pooled centring for all arms: worst-domain design limit 1.48% (recipes), within the 1.5% target.

## Intended use

First-pass triage of long-form text (essays, articles, submissions) in front of **human review**.
Not for automatic penalties, grading or accusations. A verdict is statistical evidence, not proof.

## Modes

| Mode | Model B | Notes |
|---|---|---|
| `careful` (default) | `mlx-community/Llama-3.2-1B-Instruct-4bit` (unpacked exactly on PyTorch) | Smaller download |
| `official` | `unsloth/Llama-3.2-1B-Instruct`, full precision | The setup submitted to RAID |

Each mode is compiled with its own measured contrast constants.

## Measured results (this project's harness on RAID's labelled training data, English, no attacks unless stated)

Held-out half: 3,200 human texts (400 per domain) and 1,360 AI texts (40 per generator setting, 34 settings).

**The app's own verdicts:**

| Mode | Human labelled `ai` | AI labelled `ai` | Rep. penalty | No penalty | Base-model sampling | Chat models |
|---|---|---|---|---|---|---|
| careful | 0.22% (poetry 1.25%, recipes 0.25%, reddit 0.25%, others 0%) | 78.9% | 97.3% | 68.9% | 22.5% | 86.8% |
| official | 0.22% (poetry 1.25%) | 80.8% | 97.3% | 71.8% | 23.0% | 90.1% |
| v7, careful | 1.59% (poetry 5.25%) | 67.9% | 46.7% | 79.4% | 41.5% | 83.6% |

No human text of 600 tokens or more (n = 386) was labelled `ai`. Human verdicts in careful mode: 3,133 `undecided`,
60 `no_evidence`, 7 `ai`.

**RAID's metric** (per-domain thresholds from human texts):

| Mode | 5% FPR | 1% FPR | v7 at 5% / 1% |
|---|---|---|---|
| careful | 92.4% | 87.6% | 77.1% / 65.9% |
| official | 92.9% | 88.3% | 77.5% / 65.1% |

RAID's own evaluator on a second, 8-domain sample (1,600 human, 1,320 AI): v8.1 92.5% / 86.7%, v7 82.3% / 72.4%.

**Under RAID's 11 attacks** (official mode; 220 AI and 75 human texts per attack; thresholds from clean human texts):

| Attack | 5% FPR, v7 → v8.1 | 1% FPR, v7 → v8.1 | Attacked human labelled `ai`, v7 → v8.1 |
|---|---|---|---|
| whitespace | 84.1 → 96.4 | 70.5 → 90.9 | 1.00% → 0% |
| homoglyph | 86.8 → 95.5 | 73.6 → 92.7 | 1.33% → 0% |
| zero-width space | 84.1 → 95.5 | 76.8 → 92.3 | 4.00% → 0% |
| misspelling | 83.6 → 95.5 | 71.4 → 90.0 | 1.33% → 0% |
| number | 77.7 → 93.2 | 67.3 → 90.0 | 0% → 0% |
| insert paragraphs | 80.0 → 92.7 | 72.3 → 90.9 | 4.00% → 0% |
| alternative spelling | 77.3 → 89.5 | 64.1 → 84.1 | 4.00% → 0% |
| upper/lower case | 76.8 → 88.2 | 63.6 → 81.4 | 2.67% → 0% |
| paraphrase | 70.0 → 85.9 | 49.5 → 71.8 | 24.00% → 1.33% |
| article deletion | 69.5 → 84.1 | 55.9 → 79.5 | 2.67% → 0% |
| synonym | 62.7 → 75.0 | 43.6 → 68.6 | 6.67% → 0% |
| **mean** | **77.5 → 90.1** | **64.4 → 84.8** | |

**Parity:** the package's engine (MLX on an M4 Pro) and the official A30 run (PyTorch fp16) gave identical verdicts
on 120 of 120 RAID texts; score correlation 0.99992. Careful mode on 480 held-out human texts flagged 1 (0.21%, a poem).

**Code checks** (`make test`): both modes compile under `-Wall -Wextra -Werror -std=c99`; extreme and random streams
of 2^18 tokens run clean under UBSan and ASan; a stop latches; law_score stays within 3·2^18.

## Official benchmark: RAID

RAID test set, 672,000 texts (11 generators, 8 domains, 4 sampling settings, 11 attacks), scored by RAID's evaluation
bot. Metric: share of AI texts caught at a fixed false-positive rate, thresholds set per domain from human texts.

**v8.1** (2026-10-08, [liamdugan/raid#216](https://github.com/liamdugan/raid/pull/216), official mode):

| | 5% FPR | 1% FPR | AUROC |
|---|---|---|---|
| No attacks | 92.33% | 86.54% | 97.61 |
| All texts incl. attacks | 88.99% | 81.37% | 96.48 |
| Binoculars (official), no attacks | 78.98% | 69.54% | – |
| v7 (official), no attacks / all texts | 80.08% / 77.00% | 68.92% / 63.87% | 90.56 / 89.86 |

Per domain, no attacks, 5% FPR: abstracts 89.75, books 95.01, news 91.96, poetry 89.37, recipes 91.28, reddit 92.09,
reviews 94.76, wiki 94.43 (ahead of Binoculars in all 8). Per attack, 5% FPR: whitespace, zero-width space and homoglyph
92.33 (cleaned before scoring), alternative spelling 91.64, misspelling 91.21, insert paragraphs 91.08, number 90.98,
upper/lower 88.17, article deletion 88.13, synonym 80.83, paraphrase 76.57. By sampling: greedy 97.38 (no penalty) /
99.47 (penalty); random sampling 79.95 (no penalty) / 98.64 (penalty). Rank 27 of 44 on all texts. Before the
official run we estimated 89.6% on all texts from the submitted scores; the official figure is 88.99%.

## Limits

- **Synonym swapping** hides the surprise signal (80.83% on the official test; the contrast signal carries it).
- **Paraphrase** is the hardest attack: 76.57% at 5% FPR on the official test, and the app's verdict usually stays
  `undecided` (36% labelled `ai` in our test); paraphrasers add repeats, which pushes the repetition signal the wrong way.
- **Random sampling without a repetition penalty** is the hardest setting (79.95% officially; 22.5% labelled `ai` by the app for base models).
- **Frontier models in short texts:** Claude-class text is mostly `undecided` below roughly 800–2,000 tokens.
- **AI-polished human work is flagged:** the filter sees AI wording, not the origin of the ideas.
- **More `undecided`:** v8.1 is more cautious per text than v7; most human texts end `undecided`, not `no_evidence`.
- **Narrow testing:** English only; calibrated on RAID's 8 domains. Other genres need a human baseline.
- **Accuracy ceiling:** trained classifiers score higher on RAID (up to 99.98% at 5% FPR).

The v7 model card, with its earlier measurements (IMDB, GitHub issues, medical abstracts, Claude documents), is in
[archive/v7/MODEL_CARD_v7.md](archive/v7/MODEL_CARD_v7.md).
