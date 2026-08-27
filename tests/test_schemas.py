from schemas import SCORE_KEYS, extract_json, model_identity_leak, validate_verdict

GOOD = {
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


def test_good_passes():
    assert validate_verdict(GOOD) == []


def test_bad_scores_rejected():
    bad = {**GOOD, "scores": {**GOOD["scores"], "quality": 11}}
    assert any("quality" in e for e in validate_verdict(bad))


def test_missing_hard_flags_rejected():
    bad = {k: v for k, v in GOOD.items() if k != "hard_flags"}
    assert validate_verdict(bad)


def test_identity_leak_scan():
    leaky = {**GOOD, "score_reasons": {**GOOD["score_reasons"], "quality": "typical gpt-image output"}}
    assert model_identity_leak(leaky)
    assert model_identity_leak(GOOD) == []


def test_extract_json_from_fenced():
    txt = 'bla\n```json\n{"a": 1}\n```\ntail'
    assert extract_json(txt) == {"a": 1}
