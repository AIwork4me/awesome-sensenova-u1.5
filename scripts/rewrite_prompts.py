#!/usr/bin/env python3
"""Attribution-driven prompt rewriting (spec REFINE loop).

Consumes runs/comparisons/round-{R}/report.json from compare_parity.py: every
status=="fail" row gets exactly ONE strategy chosen from its failed_checks
strings (pick_strategy), and that strategy's directive is appended to the
case's latest prompt text as adapted-v{n+1}.md. All application converges on
the pure function apply_strategy(), so swapping in an LLM rewriter later only
replaces that body, not the pipeline. Rewrites stop after MAX_REWRITE_ROUNDS
per case; further failures record a status_capped ledger event instead. When
main() runs with --round, cases already carrying a rewritten event for that
round are skipped, so operator reruns cannot stack duplicate directives.
"""
import argparse
import json
import re
import time
from pathlib import Path

from lib.constants import MAX_REWRITE_ROUNDS
from lib.ledger import append_event, load_events
from make_gen_jsonl import latest_prompt_text

STRATEGIES = {
    "S1_drop_microtext": {
        "trigger": "small_text_quality == garbled",
        "directive": ("Typography constraint: do NOT render a credits block, billing block "
                      "or any micro-print paragraph. Limit all typography to the main title "
                      "and, if specified, the subtitle and a short date/release line only."),
        "sets_small_text_exempt": True,
    },
    "S2_simplify_display_text": {
        "trigger": "display_text_correct == false or text_miss_count > 0",
        "directive": ("Typography constraint: render ONLY the required title strings; use short "
                      "letterforms, high contrast between text and background, and avoid any "
                      "decorative distortion of glyphs. Spell each word exactly as given."),
        "sets_small_text_exempt": False,
    },
    "S3_explicit_constraints": {
        "trigger": "unfulfilled mentions count/layout/position words",
        "directive": ("Composition constraints: follow the quantities below literally and place "
                      "objects as stated; prefer explicit enumeration over prose description."),
        "sets_small_text_exempt": False,
    },
    "S4_style_anchor": {
        "trigger": "default when others absent (style/aesthetic shortfall)",
        "directive": ("Style anchoring: identify the medium (flat vector poster / photographic "
                      "print / ink painting), name the palette explicitly, and reference the era "
                      "and genre in the first sentence of the prompt."),
        "sets_small_text_exempt": False,
    },
    "S5_avoid_anatomy": {
        "trigger": "visual_defects == true or unfulfilled mentions hands/face/limbs",
        "directive": ("Subject rendering constraints: favor medium or wide shots; keep hands "
                      "either naturally occupied or out of frame; avoid close-ups of faces with "
                      "complex expressions."),
        "sets_small_text_exempt": False,
    },
}
KEYWORD_RULES = [(r"\bcount\b|\bquantity\b|number of", "S3_explicit_constraints"),
                 (r"\bhand\b|\bfinger\b|\blimb\b|\bface\b|\banatom", "S5_avoid_anatomy"),
                 (r"\bcolor\b|\blayout\b|\bposition\b|\bbackground\b",
                  "S3_explicit_constraints")]


def pick_strategy(failed_checks: list[str]) -> str:
    """Classify a report row's failed_checks strings into one S1..S5 id."""
    joined = " ".join(failed_checks).lower()
    if any("c_small_text" in c for c in failed_checks):
        return "S1_drop_microtext"
    if any("b_display_text" in c or "d_miss_zero" in c for c in failed_checks):
        return "S2_simplify_display_text"
    if any("a_score_gap" in c for c in failed_checks):
        hit = None
        for pat, sid in KEYWORD_RULES:
            if re.search(pat, joined):
                if sid == "S5_avoid_anatomy":
                    return sid          # anatomy outranks composition keywords
                hit = hit or sid
        if hit:
            return hit
    if any("e_no_visual_defects" in c for c in failed_checks):
        return "S5_avoid_anatomy"
    return "S4_style_anchor"


def apply_strategy(text: str, strategy_id: str) -> str:
    """Pure rewrite step; a future LLM rewriter replaces only this body."""
    return text.rstrip() + "\n\n" + STRATEGIES[strategy_id]["directive"]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _next_version(case_dir: Path) -> int:
    """Version number for the next adapted file; base.md counts as version 1."""
    nums = []
    for p in case_dir.glob("adapted-v*.md"):
        m = re.fullmatch(r"adapted-v(\d+)\.md", p.name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) if nums else 1) + 1


def rewrite_one(case_id, failed_checks, root=Path("."), ledger="ledger/append.jsonl",
                round=None) -> str:
    """Rewrite one failing case's prompt once, respecting MAX_REWRITE_ROUNDS.

    `round`, when given, is stored in the rewritten ledger event so main() can
    skip rows already rewritten in that round on rerun. Returns "rewritten" or
    "capped"; on the capped path only a status_capped ledger event is appended
    (idem=cap-{case}) and no prompt file is touched.
    """
    lpath = root / ledger
    prior = [ev for ev in load_events(lpath)
             if ev.get("type") == "rewritten"
             and ev.get("payload", {}).get("case_id") == case_id]
    if len(prior) >= MAX_REWRITE_ROUNDS:
        append_event(lpath, "status_capped",
                     {"case_id": case_id, "capped_at_round": len(prior)},
                     idem=f"cap-{case_id}")
        return "capped"
    s = pick_strategy(failed_checks)
    case_dir = root / f"cases/pilot/case-{case_id}"
    ver = _next_version(case_dir)
    (case_dir / f"adapted-v{ver}.md").write_text(
        apply_strategy(latest_prompt_text(case_dir), s), encoding="utf-8")
    prov_p = case_dir / "provenance.json"
    prov = json.loads(prov_p.read_text(encoding="utf-8")) if prov_p.exists() else {}
    hist = prov.setdefault("history", [])
    hist.append({"version": ver, "strategy": s, "failed_checks": list(failed_checks),
                 "applied_directive": STRATEGIES[s]["directive"],
                 "small_text_exempt": STRATEGIES[s]["sets_small_text_exempt"],
                 "ts": _now()})
    prov_p.write_text(json.dumps(prov, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    append_event(lpath, "rewritten",
                 {"case_id": case_id, "version": ver, "strategy": s,
                  "failed_checks": list(failed_checks), "round": round},
                 idem=f"rw-{case_id}-{ver}")
    return "rewritten"


def _rewritten_this_round(events, case_id, rnd) -> bool:
    return any(ev.get("type") == "rewritten"
               and ev.get("payload", {}).get("case_id") == case_id
               and ev.get("payload", {}).get("round") == rnd
               for ev in events)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Attribution-driven prompt rewriting.")
    ap.add_argument("--round", type=int, default=None,
                    help="rewrite round; enables the same-round rerun guard")
    ap.add_argument("--ledger", default="ledger/append.jsonl")
    args = ap.parse_args(argv)
    root = Path(".")
    report_p = root / f"runs/comparisons/round-{args.round}/report.json"
    report = json.loads(report_p.read_text(encoding="utf-8"))
    events = load_events(root / args.ledger)
    rewrote = capped = skipped = 0
    for row in report["per_case"]:
        if row.get("status") != "fail":
            continue
        cid = row["case_id"]
        if args.round is not None and _rewritten_this_round(events, cid, args.round):
            print(f"[rewrite] case {cid} already rewritten this round; skipped")
            skipped += 1
            continue
        outcome = rewrite_one(cid, row.get("failed_checks", []), root=root,
                              ledger=args.ledger, round=args.round)
        rewrote += outcome == "rewritten"
        capped += outcome == "capped"
    print(f"[rewrite] round={args.round} rewrote={rewrote} capped={capped} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
