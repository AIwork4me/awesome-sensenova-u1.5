import json

from fixtures import GOOD_VERDICT
from schemas import extract_json, model_identity_leak, validate_verdict

# Deep-copied so suite mutations never touch the shared fixture instance.
GOOD = json.loads(json.dumps(GOOD_VERDICT))


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


def test_unhashable_small_text_quality_returns_error():
    bad = {**GOOD, "hard_flags": {**GOOD["hard_flags"], "small_text_quality": []}}
    errs = validate_verdict(bad)
    assert any("small_text_quality" in e for e in errs)


def test_extract_json_from_fenced():
    txt = 'bla\n```json\n{"a": 1}\n```\ntail'
    assert extract_json(txt) == {"a": 1}
