# Results

## v8.1 (THE DETECT LAW v8.1, detect-law 0.3.0)

| File | What it is |
|---|---|
| `raid_official_results_v81.json` | RAID's own evaluation of v8.1, committed by RAID's bot to [liamdugan/raid#216](https://github.com/liamdugan/raid/pull/216) on 2026-10-08. Every split of the 672,000-text test set. Official mode. |
| `v81_measurements.md` | v8.1 against v7 on RAID's labelled training data: measured constants, app verdicts, RAID's metric, and all 11 RAID attacks (Kaggle runs, 2026-10-07/08). |

Official RAID result for v8.1: 92.33% of AI text caught at 5% false positives without attacks (86.54% at 1%), 88.99%
on all texts including the 11 attacks (81.37% at 1%), AUROC 96.48. v7: 80.08% / 77.00%.

The rest of this page is v7's.

| File | What it is |
|---|---|
| `raid_official_results.json` | RAID's own evaluation of the submission, committed by RAID's bot to [liamdugan/raid#212](https://github.com/liamdugan/raid/pull/212) on 2026-10-06 and merged into the [leaderboard](https://raid-bench.xyz/leaderboard) the same day. Scores for every split of the 672,000-text test set. Produced in **official mode**. |
| `app_verdicts_raid_labelled_sample.jsonl` | The app's own verdicts (`ai` / `no_evidence` / `undecided`) in **official mode** on 2,920 labelled texts from RAID's training data (1,600 human, 1,320 AI, 8 domains, no attacks). |
| `app_verdicts_raid_labelled_sample_careful.jsonl` | The same 2,920 texts in **careful mode**. |

## Headline numbers

Official RAID test set, official mode, share of AI text caught at 5% false positives (RAID's thresholds are set per domain from human texts):

| | No attacks | All texts, 11 attacks |
|---|---|---|
| Detect Law v7 | 80.08% | 77.00% |
| Binoculars (official entry) | 78.98% | not submitted |

At 1% false positives without attacks: Detect Law 68.92%, Binoculars 69.54%.

The app's own verdicts use the law's fixed decision rule, not RAID's tuned thresholds. On the labelled sample:

| Mode | Human texts flagged `ai` | AI texts flagged `ai` |
|---|---|---|
| official | 27 / 1,600 = 1.7% (book summaries 8.0%, reviews 3.0%) | 885 / 1,320 = 67.0% |
| careful | 9 / 1,600 = 0.56% (book summaries 2.5%, reviews 1.0%, reddit 1.0%) | 811 / 1,320 = 61.4% |
