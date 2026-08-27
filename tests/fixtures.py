from schemas import SCORE_KEYS

GOOD_VERDICT = {
    "scores": {k: 8 for k in SCORE_KEYS},
    "score_reasons": {k: "ok" for k in SCORE_KEYS},
    "unfulfilled_requirements": [],
    "transcribed_text": ["TITLE"],
    "hard_flags": {
        "display_text_correct": True,
        "small_text_quality": "correct",
        "text_miss_count": 0,
        "visual_defects": False,
    },
}
