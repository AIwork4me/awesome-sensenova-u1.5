"""Verdict schema validation (spec Appendix B) plus LLM-output helpers."""
import json
import re

SCORE_KEYS = ["quality", "aesthetics", "alignment", "real_world_fidelity", "creative_generation"]
_SMALL_TEXT = {"correct", "mildly_deformed", "garbled"}
_BANNED = re.compile(r"gpt[-_ ]?image|sensenova|openai", re.I)


def validate_verdict(v):
    errs = []
    scores = v.get("scores")
    if not isinstance(scores, dict):
        return ["scores: missing object"]
    for k in SCORE_KEYS:
        val = scores.get(k)
        if not isinstance(val, int) or isinstance(val, bool) or not 0 <= val <= 10:
            errs.append(f"scores.{k}: must be int in [0,10]")
    reasons = v.get("score_reasons")
    if not isinstance(reasons, dict) or any(k not in reasons for k in SCORE_KEYS):
        errs.append("score_reasons: must cover all five dims")
    for key in ("unfulfilled_requirements", "transcribed_text"):
        if not isinstance(v.get(key), list):
            errs.append(f"{key}: must be list")
    hf = v.get("hard_flags")
    if not isinstance(hf, dict):
        errs.append("hard_flags: missing object")
        return errs
    if not isinstance(hf.get("display_text_correct"), bool):
        errs.append("hard_flags.display_text_correct: must be bool")
    stq = hf.get("small_text_quality")
    if not isinstance(stq, str) or stq not in _SMALL_TEXT:
        errs.append("hard_flags.small_text_quality: enum correct|mildly_deformed|garbled")
    miss = hf.get("text_miss_count")
    if not isinstance(miss, int) or isinstance(miss, bool) or miss < 0:
        errs.append("hard_flags.text_miss_count: must be int >= 0")
    if not isinstance(hf.get("visual_defects"), bool):
        errs.append("hard_flags.visual_defects: must be bool")
    return errs


def model_identity_leak(v, allowed_text=""):
    # Scan JUDGMENT fields only: score_reasons values + unfulfilled_requirements items.
    # transcribed_text is a factual transcription of visible image text and is EXEMPT
    # (e.g. a poster legitimately rendering "GPT-Image-2" must not void the verdict).
    # R17 prompt-context exemption: identity leaks are judged only OUTSIDE the prompt.
    # When a matched banned substring (casefold-compared) also appears verbatim in the
    # entry's own prompt (allowed_text), the judge is citing prompt-provided brand
    # words to assess fidelity — that is faithful description, not a leak. Each match
    # is checked individually; a text with any non-exempt match is still flagged.
    allowed = allowed_text.casefold()
    texts = [str(t) for t in v.get("unfulfilled_requirements", [])]
    reasons = v.get("score_reasons") or {}
    texts += [str(x) for x in reasons.values()]
    out = []
    for t in texts:
        if any(m.group(0).casefold() not in allowed for m in _BANNED.finditer(t)):
            out.append(t[:120])
    return out


def extract_json(text):
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    start = None
    return None
