#!/usr/bin/env python3
"""Validate judge outputs, enrich envelopes, persist receipts (spec §6.4)."""
import argparse
import json
import shutil
import time
from pathlib import Path

from lib.ledger import append_event
from lib.schemas import model_identity_leak, validate_verdict


def _collect_round(rnd: int, ledger: str, root: Path = Path(".")) -> int:
    q = root / f"runs/judge-queue/round-{rnd}"
    man = {m["entry_id"]: m for m in json.loads((q / "manifest.json").read_text())}
    inv = q / "verdicts-invalid"
    n_bad = 0
    for eid, m in man.items():
        vp = q / "verdicts" / f"{eid}.json"
        outp = root / "results/judge" / f"{eid}.json"
        if not vp.exists() or outp.exists():
            continue
        try:
            verdict = json.loads(vp.read_text())
        except json.JSONDecodeError:
            verdict = None
        errs = validate_verdict(verdict) if isinstance(verdict, dict) else ["not a json object"]
        leaks = model_identity_leak(verdict) if isinstance(verdict, dict) else ["n/a"]
        if errs or leaks:
            inv.mkdir(parents=True, exist_ok=True)
            shutil.move(str(vp), str(inv / f"{eid}.json"))
            append_event(root / ledger, "judge_failed",
                         {"entry_id": eid, "errors": errs[:3], "leaks": leaks[:1]}, idem=eid)
            n_bad += 1
            continue
        env = {"schema_version": "1.0", "entry_id": eid, "backend": "agent",
               "judged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "source": m["source"], "case_id": m["case_id"],
               "round": m["round"], "seed": m["seed"], "verdict": verdict}
        outp.write_text(json.dumps(env, ensure_ascii=False, indent=1), encoding="utf-8")
        if m["source"] == "reference":
            bp = root / f"results/judge/_baseline/{m['case_id']}.json"
            bp.write_text(json.dumps(env, ensure_ascii=False, indent=1), encoding="utf-8")
        append_event(root / ledger, "judged",
                     {"entry_id": eid, "source": m["source"], "case_id": m["case_id"],
                      "results_path": str(outp)}, idem=eid)
    print(f"[collect] round={rnd} persisted={len(man) - n_bad} invalid={n_bad}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--ledger", default="ledger/append.jsonl")
    a = ap.parse_args(argv)
    return _collect_round(a.round, a.ledger)


if __name__ == "__main__":
    raise SystemExit(main())
