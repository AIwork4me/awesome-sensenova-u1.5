#!/usr/bin/env python3
"""Build the blind self-consistency resample task list for one round.

Fixes the resample selection into a testable program (operator-loop §3):
reads the round manifest via the shared private-first resolver, selects
ceil(entries * RESAMPLE_RATE) entry ids deterministically, and writes
  runs/judge-queue/round-N/resample-tasks.jsonl
      (same row schema as tasks.jsonl, verdict_path pointed at
       verdicts-resample/; carries no source/provenance fields)
plus selection provenance next to the manifest (queue dir by default,
judge-private dir under --isolated):
  resample-selection.json {round, seed, n_entries, n_selected, selected_entry_ids}

Selection is deterministic: manifest entries sorted by entry_id,
random.Random(sha256("resample-{round}")). The script never contacts any
judge. It refuses to overwrite an existing resample-tasks.jsonl unless
--force, so historical frozen artifacts (e.g. round-1's archived selection,
which predates this script) stay untouched.
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from lib.constants import RESAMPLE_RATE
from lib.judge_manifest import manifest_path


def select_ids(entries: list[dict], round_id: int) -> tuple[str, list[str]]:
    """Deterministic blind resample selection; returns (seed, sorted ids)."""
    seed = hashlib.sha256(f"resample-{round_id}".encode()).hexdigest()
    n = math.ceil(len(entries) * RESAMPLE_RATE)
    ids = sorted(e["entry_id"] for e in entries)
    return seed, random.Random(int(seed[:16], 16)).sample(ids, n)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the round's resample task list.")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--isolated", action="store_true",
                    help="write selection provenance under runs/judge-private/ "
                         "(manifest is resolved private-first either way)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing resample-tasks.jsonl")
    args = ap.parse_args(argv)

    root = Path(".")
    q = root / f"runs/judge-queue/round-{args.round}"
    man = json.loads(manifest_path(root, args.round).read_text(encoding="utf-8"))
    seed, selected = select_ids(man, args.round)

    sel_dir = (root / f"runs/judge-private/round-{args.round}") if args.isolated else q
    sel_dir.mkdir(parents=True, exist_ok=True)
    sel_payload = {"round": args.round, "seed": seed, "n_entries": len(man),
                   "n_selected": len(selected), "selected_entry_ids": selected,
                   "rate": RESAMPLE_RATE}
    (sel_dir / "resample-selection.json").write_text(
        json.dumps(sel_payload, ensure_ascii=False, indent=1), encoding="utf-8")

    out = q / "resample-tasks.jsonl"
    if out.exists() and not args.force:
        print(f"[resample] {out} already exists; pass --force to overwrite "
              "(historical artifacts are never clobbered by default)")
        return 0
    by_id = {m["entry_id"]: m for m in man}
    with out.open("w", encoding="utf-8") as f:
        for eid in selected:
            m = by_id[eid]
            f.write(json.dumps({
                "entry_id": eid,
                "image_path": m["orig_image"],
                "prompt_path": str(q / "prompts" / f"{eid}.txt"),
                "verdict_path": str(q / "verdicts-resample" / f"{eid}.json"),
            }) + "\n")
    print(f"[resample] round={args.round} entries={len(man)} selected={len(selected)} "
          f"tasks={out} selection={sel_dir / 'resample-selection.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
