"""What has been measured, in one place: served by /v1/info and the MCP `about_detect_law` tool."""

RAID = {
    "source": "Official RAID test set (672,000 texts), scored by RAID's evaluation bot on 2026-10-06 and listed on "
              "raid-bench.xyz/leaderboard (github.com/liamdugan/raid/pull/212). Produced in official mode.",
    "metric": "share of AI texts caught at a fixed false-positive rate on human texts (per-domain thresholds)",
    "all_texts_including_attacks": {"at_5pct_fpr": 77.00, "at_1pct_fpr": 63.87, "auroc": 89.86},
    "no_attacks": {"at_5pct_fpr": 80.08, "at_1pct_fpr": 68.92, "auroc": 90.56},
    "binoculars_official_no_attacks": {"at_5pct_fpr": 78.98, "at_1pct_fpr": 69.54},
    "standing": "Highest no-attack score at 5% FPR among the zero-shot detectors on the RAID leaderboard "
                "(Binoculars 78.98, GLTR 59.69, LLMDet 33.40). Binoculars is slightly ahead at 1% FPR. "
                "Trained classifiers score higher (up to 99.98); overall rank 34 of 43.",
    "per_domain_no_attacks_5pct": {"abstracts": 86.7, "books": 83.7, "news": 82.0, "poetry": 75.3, "recipes": 73.9,
                                   "reddit": 77.8, "reviews": 78.4, "wiki": 82.9},
    "per_attack_5pct": {"none": 80.1, "whitespace": 80.1, "zero_width_space": 80.1, "homoglyph": 80.1,
                        "alternative_spelling": 78.8, "insert_paragraphs": 78.5, "number": 78.4,
                        "perplexity_misspelling": 78.4, "article_deletion": 74.9, "upper_lower": 74.5,
                        "synonym": 71.7, "paraphrase": 68.3},
    "binoculars_per_attack_5pct": {"none": 79.0, "whitespace": 68.7, "zero_width_space": 98.4, "homoglyph": 36.1,
                                   "alternative_spelling": 77.6, "insert_paragraphs": 70.7, "number": 76.4,
                                   "perplexity_misspelling": 77.2, "article_deletion": 73.3, "upper_lower": 72.8,
                                   "synonym": 42.1, "paraphrase": None},
    "attack_standing": "Ahead of Binoculars on 9 of the 10 attacks both were scored on (average 77.6 vs 69.3); "
                       "Binoculars has no paraphrase result. Trained classifiers stay near 99% under paraphrase.",
}

INFO = {
    "law": "v7",
    "what": "An exact 32-bit integer decision rule over two signals from two open 1.24B-parameter models "
            "(Llama 3.2 1B base and Instruct). No training on labelled AI text (zero-shot).",
    "verdicts": {"ai": "statistical evidence of AI generation: send to human review",
                 "no_evidence": "an AI-sized effect was ruled out for the generators covered; not proof of human authorship",
                 "undecided": "not enough evidence, usually a short text; draw no conclusion"},
    "false_positive_design_bound": "at most 1% of human texts labelled ai, for text like the calibration data "
                                   "(anytime-valid early stop + end-of-text test)",
    "modes": {"careful": "default; B = Llama-3.2-1B-Instruct 4-bit, the model the contrast term was calibrated on",
              "official": "B = Llama-3.2-1B-Instruct full precision, the setup scored on RAID"},
    "app_verdicts_measured": {
        "data": "2,920 labelled RAID training texts: 1,600 human, 1,320 AI, 8 domains, no attacks",
        "careful": {"human_flagged_ai": "9/1600 = 0.56% (book summaries 2.5%, reviews 1.0%, reddit 1.0%, others 0%)",
                    "ai_flagged_ai": "811/1320 = 61.4%"},
        "official": {"human_flagged_ai": "27/1600 = 1.69% (book summaries 8.0%, reviews 3.0%, reddit 1.5%)",
                     "ai_flagged_ai": "885/1320 = 67.0%"}},
    "raid_official": RAID,
    "speed_measured": {"nvidia_a40": "12,792 tokens/s (0.10 s per 1,000 words)",
                       "apple_m4_pro_gpu": "about 900 tokens/s (1.4 s per 1,000 words)",
                       "cpu_4_cores": "about 430 tokens/s (3 s per 1,000 words)"},
    "cost": "Runs on your own machine: free, no word limit. On a rented A40 GPU, 3 billion words take about "
            "84 GPU-hours, roughly $40.",
    "known_limits": ["frontier models (Claude-class) are weakly detected in short texts; long documents are much stronger",
                     "paraphrasing lowers detection (68.3% on RAID's paraphrase attack)",
                     "human text heavily rewritten by an AI tool is flagged as AI",
                     "English only",
                     "reference models are Llama 3.2 1B (Built with Llama; Llama 3.2 Community License)"],
    "intended_use": "triage for human review; never automatic penalties or accusations",
}
