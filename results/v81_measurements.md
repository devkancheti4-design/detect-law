# THE DETECT LAW v8.1 vs v8 vs v7 (Kaggle 2 x T4, version 7, 2026-10-07)

Same data as the v8 test: 3,200 held-out human RAID training texts (400 per domain) and 1,360 AI texts (34 cells), no attacks.
Constants measured as V81_DERIVATION.md section 3 on the 3,200 calibration texts.

## Measured (careful mode; A and R identical in official mode)
| arm | c pooled | c worst | within-text rho | kappa_w (worst domain) |
|---|---|---|---|---|
| A surprise | +0.00953 | +0.01606 recipes | 0.811 | 0.01348 recipes (abstracts 0.0) |
| C contrast | +0.05293 | +0.07651 poetry | 1.000 (0.972 measured, capped at >=1) | 0.03560 poetry |
| R repetition | -0.07434 | -0.02323 abstracts | 1.013 | 0.11097 poetry (abstracts, books, news 0.0) |
v81_gen.py accepted all-pooled centring: worst-domain limit 1.482% (recipes) <= 1.5%.

## App verdicts
| mode | law | human flagged | worst domain | long human (>=600 tok, n=386) | all AI | rep. penalty | no penalty | base sampling | base + penalty | chat |
|---|---|---|---|---|---|---|---|---|---|---|
| careful | v7 | 1.59% | poetry 5.25% | 5.18% | 67.9% | 46.7% | 79.4% | 41.5% | 23.8% | 83.6% |
| careful | v8 (B every token) | 0.28% | poetry 1.75% | 0.52% | 77.8% | 96.9% | 67.4% | 20.0% | 97.1% | 86.9% |
| careful | **v8.1** | **0.22%** | poetry 1.25% | **0.00%** | **78.9%** | **97.3%** | 68.9% | 22.5% | **97.9%** | 86.8% |
| official | v7 | 2.84% | books 8.25% | 10.36% | 72.1% | 53.8% | 82.2% | 45.0% | 24.6% | 89.9% |
| official | **v8.1** | **0.22%** | poetry 1.25% | **0.00%** | **80.8%** | **97.3%** | 71.8% | 23.0% | **97.9%** | **90.1%** |
v8.1 per-domain human flags (careful): poetry 1.25%, recipes 0.25%, reddit 0.25%, others 0%.
v8.1 verdicts, careful: AI = ai 1,073 / undecided 287 / no evidence 0; human = undecided 3,133 / no evidence 60 / ai 7.

## RAID metric (ranking by law_score, per-domain thresholds from held-out human scores)
| mode | FPR | v7 | v8 (B every token) | v8.1 |
|---|---|---|---|---|
| careful | 5% | 77.1% | 88.2% | **92.4%** |
| careful | 1% | 65.9% | 83.2% | **87.6%** |
| official | 5% | 77.5% | 89.0% | **92.9%** |
| official | 1% | 65.1% | 82.4% | **88.3%** |
v8.1 subsets, careful, 5%: rep. penalty 99.8, no penalty 88.4 (v7 88.2), base sampling 57.5 (v7 62.0), base + penalty 99.6, chat 98.3 (v7 90.7).

## Per-arm median z (v8.1, careful)
A: human +0.06 | rep-pen +0.32 | no-pen +2.69 | base-samp +1.70 | base+pen -1.47 | chat +2.22
C: human -0.03 | rep-pen +1.32 | no-pen +2.36 | base-samp +0.85 | base+pen +0.29 | chat +3.25
R: human -0.02 | rep-pen +5.32 | no-pen -0.48 | base-samp -0.32 | base+pen +6.44 | chat +0.57

## Targets
Met: human <= 1% (0.22%), worst domain <= 1.5% (poetry 1.25%), penalty >= 95% (97.3%), ranking >= 88% / 83% (92.4 / 87.6), chat >= 87% (official 90.1; careful 86.8).
Missed: app verdicts on AI without penalty (68.9% vs 79%) and base-model sampling (22.5% vs 41%).
Not tested: adversarial attacks (paraphrase, synonyms); official RAID test set.

## Under RAID's 11 attacks (Kaggle notebook975d896532, report_attack.txt, 2026-10-08)
3,270 attacked texts (220 AI + 75 human per attack, 100 human for whitespace); thresholds per domain from the CLEAN held-out human texts, as RAID's evaluator does.
Official mode: AI caught @5% FPR v7 -> v8.1 | @1% v7 -> v8.1 | app verdict on AI v7 -> v8.1 | app verdict on attacked HUMAN v7 -> v8.1
| attack | @5% | @1% | app AI flagged | app human flagged |
|---|---|---|---|---|
| alternative_spelling | 77.3 -> **89.5** | 64.1 -> 84.1 | 66.4 -> 74.5 | 4.00 -> 0.00 |
| article_deletion | 69.5 -> **84.1** | 55.9 -> 79.5 | 61.8 -> 65.5 | 2.67 -> 0.00 |
| homoglyph | 86.8 -> **95.5** | 73.6 -> 92.7 | 79.5 -> 80.5 | 1.33 -> 0.00 |
| insert_paragraphs | 80.0 -> **92.7** | 72.3 -> 90.9 | 77.3 -> 77.7 | 4.00 -> 0.00 |
| number | 77.7 -> **93.2** | 67.3 -> 90.0 | 69.1 -> 79.1 | 0.00 -> 0.00 |
| paraphrase | 70.0 -> **85.9** | 49.5 -> 71.8 | 52.3 -> 36.4 | 24.00 -> 1.33 |
| perplexity_misspelling | 83.6 -> **95.5** | 71.4 -> 90.0 | 73.2 -> 77.3 | 1.33 -> 0.00 |
| synonym | 62.7 -> **75.0** | 43.6 -> 68.6 | 50.0 -> 48.6 | 6.67 -> 0.00 |
| upper_lower | 76.8 -> **88.2** | 63.6 -> 81.4 | 63.6 -> 70.5 | 2.67 -> 0.00 |
| whitespace | 84.1 -> **96.4** | 70.5 -> 90.9 | 77.7 -> 81.4 | 1.00 -> 0.00 |
| zero_width_space | 84.1 -> **95.5** | 76.8 -> 92.3 | 77.7 -> 80.0 | 4.00 -> 0.00 |
| **mean over attacks** | 77.5 -> **90.1** | 64.4 -> **84.8** | | |
Careful mode mean: 77.0 -> 90.1 (@5%), 65.2 -> 83.1 (@1%).
Median z of AI texts under synonym: A +0.11 (surprise arm blinded), C +1.82; under paraphrase: A +2.42, C +1.16, R -1.11 (paraphrase adds repeats).
Cross-check: v7's attack mean here (77.5 / 64.4) is within 0.5 pt of v7's official all-attack result (77.00 / 63.87), so v8.1 official all-attack ~89.6% @5% and ~84% @1%. The 5% figure matches the estimate made from the real test scores (89.6%).
