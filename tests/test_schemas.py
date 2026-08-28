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


def test_identity_leak_exempt_transcribed_text():
    v = {**GOOD, "transcribed_text": GOOD["transcribed_text"] + ["Celebrating GPT-Image-2"]}
    assert model_identity_leak(v) == []


def test_identity_leak_still_flags_score_reasons():
    leaky = {**GOOD, "score_reasons": {**GOOD["score_reasons"], "alignment": "renders GPT-Image-2 branding"}}
    flagged = model_identity_leak(leaky)
    assert flagged and "GPT-Image-2" in flagged[0]


def test_identity_leak_prompt_context_exempt():
    # R17: brand words quoted from the entry's own prompt are fidelity wording.
    leaky = {**GOOD, "score_reasons": {**GOOD["score_reasons"], "alignment": "renders GPT-Image-2 branding"}}
    assert model_identity_leak(leaky, allowed_text="海报标题：热烈庆祝GPT-Image-2 发布") == []


def test_identity_leak_flagged_when_allowed_text_lacks_term():
    leaky = {**GOOD, "score_reasons": {**GOOD["score_reasons"], "alignment": "renders GPT-Image-2 branding"}}
    flagged = model_identity_leak(leaky, allowed_text="an unrelated prompt about a cat")
    assert flagged and "GPT-Image-2" in flagged[0]


def test_identity_leak_exempt_only_matching_substrings():
    # Multiple matches: exempted ones pardon only themselves; any other hit still leaks.
    leaky = {**GOOD, "score_reasons": {**GOOD["score_reasons"],
                                       "quality": "gpt-image style, yet the @OpenAI logo is invented"}}
    assert model_identity_leak(leaky, allowed_text="draw an OpenAI logo") != []
    assert model_identity_leak(leaky, allowed_text="gpt-image style with an OpenAI logo") == []


def test_unhashable_small_text_quality_returns_error():
    bad = {**GOOD, "hard_flags": {**GOOD["hard_flags"], "small_text_quality": []}}
    errs = validate_verdict(bad)
    assert any("small_text_quality" in e for e in errs)


def test_extract_json_from_fenced():
    txt = 'bla\n```json\n{"a": 1}\n```\ntail'
    assert extract_json(txt) == {"a": 1}
