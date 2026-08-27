#!/usr/bin/env python3
"""Formal parity decision engine (spec §8).

Per case and round: pick the best-of-N sensenova envelope (highest five-dim
mean), compare it against the baseline reference envelope under five checks
(a-e), classify parity/win/fail, write runs/comparisons/round-{R}/report.json,
emit `compared` ledger events (plus freezing `status_parity` events) keyed
cmp-{R}-{case}, and print a console summary table.

Partial rounds are expected: a case whose baseline reference has not been
judged yet (or that has no candidate verdict this round) is reported as
"deferred" instead of crashing, is excluded from the milestone denominator,
and gets no ledger event.
"""
import argparse
import json
from pathlib import Path

from lib.constants import GAP_ALLOW, PARITY_RATIO, PILOT_SIZE
from lib.ledger import append_event, load_events
from lib.schemas import SCORE_KEYS

# Milestone target derived from constants, never hard-coded: 30 cases * 0.8.
TARGET_PARITY = round(PILOT_SIZE * PARITY_RATIO)

CHECKS = ("a_score_gap", "b_display_text", "c_small_text", "d_miss_zero", "e_no_visual_defects")
_FAIL_TEXT = {
    "a_score_gap": "five-dim mean below reference beyond allowance",
    "b_display_text": "display text incorrect",
    "c_small_text": "garbled small text",
    "d_miss_zero": "text missing elements",
    "e_no_visual_defects": "visual defects present",
}


def mean(env):
    return sum(env["verdict"]["scores"][k] for k in SCORE_KEYS) / len(SCORE_KEYS)


def exempt(case_id, root=Path(".")):
    """True when the case's current provenance version waives small-text garble."""
    p = root / f"cases/pilot/case-{case_id}/provenance.json"
    if not p.exists():
        return False
    hist = json.loads(p.read_text(encoding="utf-8")).get("history", [])
    return bool(hist and hist[-1].get("small_text_exempt"))


def decide(env_cand, env_ref, is_exempt):
    """Classify one candidate against its reference; returns the report row body."""
    mcand, mref = mean(env_cand), mean(env_ref)
    gap = mcand - mref
    hf = env_cand["verdict"]["hard_flags"]
    checks = {
        "a_score_gap": (mcand - mref) >= GAP_ALLOW,
        "b_display_text": hf["display_text_correct"],
        "c_small_text": (hf["small_text_quality"] != "garbled") or is_exempt,
        "d_miss_zero": hf["text_miss_count"] == 0,
        "e_no_visual_defects": not hf["visual_defects"],
    }
    status = "parity" if all(checks.values()) else "fail"
    # "win" requires beating the reference outright; if the c-check only passed
    # via the exemption the case is rescued, not genuinely better, so it stays
    # parity (matches the exemption boundary test in tests/test_compare.py).
    rescued = hf["small_text_quality"] == "garbled" and is_exempt
    if status == "parity" and mcand > mref and not rescued:
        status = "win"          # informational bonus label
    failed = [f"{k}: {_FAIL_TEXT[k]}" for k in CHECKS if not checks[k]]
    return {"candidate_mean": round(mcand, 4), "reference_mean": round(mref, 4),
            "gap": round(gap, 4), "checks": checks, "status": status,
            "failed_checks": failed}


def _load_json(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def best_candidates(root: Path, rnd: int) -> dict:
    """Best-of-N: highest-mean sensenova envelope per case for one round."""
    jroot = root / "results/judge"
    best = {}
    for p in sorted(jroot.glob("*.json")):
        env = _load_json(p)
        if not isinstance(env, dict):
            continue
        if env.get("source") != "sensenova" or env.get("round") != rnd:
            continue
        try:
            m = mean(env)
        except (KeyError, TypeError):
            continue
        cid = env.get("case_id")
        cur = best.get(cid)
        if cur is None or m > cur[0] or (m == cur[0] and env.get("entry_id", "") < cur[1].get("entry_id", "")):
            best[cid] = (m, env)
    return {cid: env for cid, (m, env) in best.items()}


def generated_files(ledger_path) -> dict:
    """tag -> file from `generated` ledger events (winner_file lookup)."""
    return {ev["payload"]["tag"]: ev["payload"]["file"]
            for ev in load_events(ledger_path) if ev.get("type") == "generated"}


def _print_table(report):
    print(f"[compare] round={report['round']} decided={len(report['per_case'])} "
          f"deferred={len(report['deferred'])}")
    print(f"{'CASE':<6} {'STATUS':<9} {'CAND':>5} {'REF':>5} {'GAP':>6}  FAILED")
    for r in report["per_case"]:
        bad = r["failed_checks"][0] if r["failed_checks"] else "-"
        print(f"{r['case_id']:<6} {r['status']:<9} {r['candidate_mean']:>5.2f} "
              f"{r['reference_mean']:>5.2f} {r['gap']:>+6.2f}  {bad}")
    m = report["milestone"]
    print(f"[compare] milestone parity={m['parity_count']} win={m['win_count']} "
          f"ratio={m['parity_ratio']:.2f} target={m['target']} total={m['total']} "
          f"overall_gap={m['overall_gap']:+.2f}")
    if report["deferred"]:
        print(f"[compare] deferred (excluded from ratio): {report['deferred']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Formal parity decision (spec section 8).")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--ledger", default="ledger/append.jsonl")
    a = ap.parse_args(argv)
    root = Path(".")
    lock = json.loads((root / "configs/pilot.lock.json").read_text(encoding="utf-8"))
    cands = best_candidates(root, a.round)
    gfiles = generated_files(root / a.ledger)
    base_dir = root / "results/judge/_baseline"

    per_case, deferred = [], []
    for meta in lock["cases"]:
        cid = meta["id"]
        benv = _load_json(base_dir / f"{cid}.json")     # missing baseline => deferred (R12)
        if cid not in cands or benv is None:
            reason = "no_baseline" if benv is None else "no_candidate"
            print(f"[compare] deferred case={cid} reason={reason}")
            deferred.append(cid)
            continue
        row = decide(cands[cid], benv, exempt(cid, root))
        wenv = cands[cid]
        row.update({"case_id": cid, "winner_entry_id": wenv.get("entry_id"),
                    "winner_seed": wenv.get("seed"),
                    "winner_file": gfiles.get(f"case{cid}-r{a.round}-s{wenv.get('seed')}")})
        per_case.append(row)
        idem = f"cmp-{a.round}-{cid}"
        payload = {k: row[k] for k in ("case_id", "status", "candidate_mean", "reference_mean",
                                       "gap", "checks", "failed_checks",
                                       "winner_entry_id", "winner_file", "winner_seed")}
        payload["round"] = a.round
        append_event(root / a.ledger, "compared", payload, idem=idem)
        if row["status"] in ("parity", "win"):
            append_event(root / a.ledger, "status_parity",
                         {"case_id": cid, "round": a.round, "status": row["status"]}, idem=idem)

    wins = sum(1 for r in per_case if r["status"] == "win")
    pars = sum(1 for r in per_case if r["status"] == "parity")
    total = len(per_case)
    milestone = {
        "parity_count": pars,
        "win_count": wins,
        "target": TARGET_PARITY,
        "total": total,
        "parity_ratio": round((pars + wins) / total, 4) if total else 0.0,
        "overall_gap": round(sum(r["gap"] for r in per_case) / total, 4) if total else 0.0,
    }
    report = {"round": a.round, "per_case": per_case, "deferred": sorted(deferred),
              "milestone": milestone}
    outdir = root / f"runs/comparisons/round-{a.round}"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    _print_table(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
