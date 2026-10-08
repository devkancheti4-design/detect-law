"""What has been measured, in one place: served by /v1/info and the MCP `about_detect_law` tool."""

RAID_V7 = {
    "source": "Official RAID test set (672,000 texts), scored by RAID's evaluation bot on 2026-10-06 and listed on "
              "raid-bench.xyz/leaderboard (github.com/liamdugan/raid/pull/212). THE DETECT LAW v7, official mode.",
    "metric": "share of AI texts caught at a fixed false-positive rate on human texts (per-domain thresholds)",
    "all_texts_including_attacks": {"at_5pct_fpr": 77.00, "at_1pct_fpr": 63.87, "auroc": 89.86},
    "no_attacks": {"at_5pct_fpr": 80.08, "at_1pct_fpr": 68.92, "auroc": 90.56},
    "binoculars_official_no_attacks": {"at_5pct_fpr": 78.98, "at_1pct_fpr": 69.54},
    "standing": "Highest no-attack score at 5% FPR among the zero-shot detectors on the RAID leaderboard "
                "(Binoculars 78.98, GLTR 59.69, LLMDet 33.40). Binoculars is slightly ahead at 1% FPR. "
                "Trained classifiers score higher (up to 99.98); overall rank 34 of 43.",
}

RAID_V81 = {
    "source": "Official RAID test set (672,000 texts), scored by RAID's evaluation bot on 2026-10-08 "
              "(github.com/liamdugan/raid/pull/216, awaiting merge to the leaderboard). THE DETECT LAW v8.1, official mode.",
    "all_texts_including_attacks": {"at_5pct_fpr": 88.99, "at_1pct_fpr": 81.37, "auroc": 96.48},
    "no_attacks": {"at_5pct_fpr": 92.33, "at_1pct_fpr": 86.54, "auroc": 97.61},
    "standing": "Highest score among zero-shot detectors on RAID: 92.33 vs Binoculars 78.98 without attacks at 5% FPR "
                "(86.54 vs 69.54 at 1%). Ahead of Binoculars in all 8 domains. Rank 27 of 44 on all texts; trained "
                "classifiers score higher (up to 99.98). Ahead of DivEye (trained) on all texts: 88.99 vs 80.62.",
    "per_domain_no_attacks_5pct": {"abstracts": 89.75, "books": 95.01, "news": 91.96, "poetry": 89.37, "recipes": 91.28,
                                   "reddit": 92.09, "reviews": 94.76, "wiki": 94.43},
    "per_attack_5pct": {"none": 92.33, "whitespace": 92.33, "zero_width_space": 92.33, "homoglyph": 92.33,
                        "alternative_spelling": 91.64, "perplexity_misspelling": 91.21, "insert_paragraphs": 91.08,
                        "number": 90.98, "upper_lower": 88.17, "article_deletion": 88.13, "synonym": 80.83,
                        "paraphrase": 76.57},
    "held_out_raid_train_no_attacks": {
        "data": "3,200 held-out human + 1,360 AI RAID training texts (34 generator settings), thresholds from human texts",
        "official_mode": {"at_5pct_fpr": 92.9, "at_1pct_fpr": 88.3},
        "careful_mode": {"at_5pct_fpr": 92.4, "at_1pct_fpr": 87.6},
        "v7_same_texts_official_mode": {"at_5pct_fpr": 77.5, "at_1pct_fpr": 65.1}},
    "raid_evaluator_on_8_domain_sample": {"v8.1": {"at_5pct_fpr": 92.5, "at_1pct_fpr": 86.7},
                                          "v7": {"at_5pct_fpr": 82.3, "at_1pct_fpr": 72.4}},
    "attacks_official_mode_5pct": {
        "data": "11 RAID attacks, 220 AI + 75 human texts each; thresholds from clean human texts (as RAID does)",
        "v8.1": {"whitespace": 96.4, "homoglyph": 95.5, "zero_width_space": 95.5, "perplexity_misspelling": 95.5,
                 "number": 93.2, "insert_paragraphs": 92.7, "alternative_spelling": 89.5, "upper_lower": 88.2,
                 "paraphrase": 85.9, "article_deletion": 84.1, "synonym": 75.0, "mean": 90.1},
        "v7": {"whitespace": 84.1, "homoglyph": 86.8, "zero_width_space": 84.1, "perplexity_misspelling": 83.6,
               "number": 77.7, "insert_paragraphs": 80.0, "alternative_spelling": 77.3, "upper_lower": 76.8,
               "paraphrase": 70.0, "article_deletion": 69.5, "synonym": 62.7, "mean": 77.5},
        "mean_at_1pct_fpr": {"v8.1": 84.8, "v7": 64.4},
        "attacked_human_texts_flagged_ai": {"v8.1": "0% on 10 attacks, 1.33% under paraphrase",
                                            "v7": "0-6.7%, 24% under paraphrase"}},
    "estimate_before_official": "From the submitted scores we had estimated 89.6% on all texts; the official result is 88.99%.",
}

INFO = {
    "law": "v8.1",
    "what": "An exact 32-bit integer sequential decision law over three per-token signals from two open 1.24B-parameter "
            "models (Llama 3.2 1B base and Instruct): surprise, contrast and repetition. No training on labelled AI "
            "text (zero-shot); its constants are measured on human text only.",
    "verdicts": {"ai": "statistical evidence of AI generation: send to human review",
                 "no_evidence": "every signal ruled out an AI-sized effect for the generators covered; not proof of human authorship",
                 "undecided": "no significant AI evidence, but not ruled out either (most human texts end here); draw no conclusion"},
    "false_positive_design_bound": "at most 1% of human texts labelled ai, including texts with their own persistent "
                                   "style bias (heterogeneity term), for text like the calibration data",
    "modes": {"careful": "default; B = Llama-3.2-1B-Instruct 4-bit",
              "official": "B = Llama-3.2-1B-Instruct full precision, the setup submitted to RAID"},
    "app_verdicts_measured": {
        "data": "3,200 held-out human + 1,360 AI RAID training texts, 8 domains, no attacks",
        "careful": {"human_flagged_ai": "7/3200 = 0.22% (poetry 1.25%, recipes 0.25%, reddit 0.25%, others 0%); "
                                        "0% of human texts over 600 tokens",
                    "ai_flagged_ai": "78.9% (97.3% with repetition penalty, 68.9% without, 86.8% chat models)"},
        "official": {"human_flagged_ai": "0.22% (poetry 1.25%)", "ai_flagged_ai": "80.8% (chat models 90.1%)"},
        "v7_for_comparison": {"careful": "human 1.59%, AI 67.9%", "official": "human 2.84%, AI 72.1%"}},
    "raid_official": RAID_V81,
    "raid_official_v7": RAID_V7,
    "parity": "The package's engine reproduces the official A30 run: 120/120 identical verdicts, score correlation 0.99992.",
    "speed_measured": {"nvidia_a30": "about 9,500 tokens/s (official run, 672,000 texts in 5.6 h)",
                       "nvidia_t4": "about 2,200 tokens/s per GPU",
                       "apple_m4_pro_gpu": "about 750 tokens/s (1.7 s per 1,000 words)"},
    "cost": "Runs on your own machine: free, no word limit. On a rented A30 GPU (about $1/hour), 3 billion words "
            "(about 3.9 billion tokens) take about 115 GPU-hours, roughly $115.",
    "known_limits": ["paraphrasing is the hardest RAID attack (76.6% caught at 5% FPR on the official test); the app's "
                     "verdict on paraphrased AI text usually stays undecided",
                     "synonym swapping weakens the surprise signal (80.8% on the official test)",
                     "AI text sampled from base models without a repetition penalty is the hardest case (22.5% flagged)",
                     "frontier models (Claude-class) are weakly detected in short texts",
                     "human text heavily rewritten by an AI tool is flagged as AI",
                     "English only",
                     "reference models are Llama 3.2 1B (Built with Llama; Llama 3.2 Community License)"],
    "intended_use": "triage for human review; never automatic penalties or accusations",
}
