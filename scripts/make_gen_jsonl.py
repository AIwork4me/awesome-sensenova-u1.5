#!/usr/bin/env python3
"""Build one batched JSONL per generation round (spec §5 GENERATE).

Cases already carrying a terminal ledger decision (`status_parity` or
`status_capped`, written by compare_parity/rewrite_prompts) are frozen: they
are skipped entirely so later rounds never regenerate for them (parity freezes;
capped freezes too per spec §5 收敛). A `[gen-jsonl] frozen=N` summary line
reports how many lock cases were excluded.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from lib.constants import SEEDS_PER_PROMPT
from lib.ledger import append_event, latest, load_events

TERMINAL_EVENT_TYPES = ("status_parity", "status_capped")

BUCKETS = [(("vertical", "portrait", "poster", "book cover"), (1664, 2496)),
           (("horizontal", "landscape", "widescreen", "banner"), (2496, 1664)),
           ((None,), (2048, 2048))]


def bucket_for(prompt: str):
    low = prompt.lower()
    for keys, wh in BUCKETS[:-1]:
        if any(k in low for k in keys):
            return wh
    return BUCKETS[-1][1]


def stable_seed(case_id, rnd, k) -> int:
    h = hashlib.blake2b(f"{case_id}|{rnd}|{k}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big") % (2**31 - 1)


def frozen_case_ids(events) -> set:
    """Lock case ids with any terminal decision event; presence means frozen
    regardless of which terminal type came last (both types freeze)."""
    out = set()
    for ev in events:
        if ev.get("type") in TERMINAL_EVENT_TYPES:
            cid = (ev.get("payload") or {}).get("case_id")
            if cid is not None:
                out.add(str(cid))
    return out


def latest_prompt_text(case_dir: Path) -> str:
    adapteds = sorted(case_dir.glob("adapted-v*.md"))
    src = adapteds[-1] if adapteds else case_dir / "base.md"
    return src.read_text(encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--ledger", default="ledger/append.jsonl")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    out = Path(args.out or f"runs/gen/round-{args.round}/gen.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    events = load_events(args.ledger)
    done = {ev["payload"]["tag"] for ev in events if ev["type"] == "generated"}
    frozen = frozen_case_ids(events)
    lock = json.loads(Path("configs/pilot.lock.json").read_text())
    lines = []
    n_frozen = 0
    for c in lock["cases"]:
        cid = c["id"]
        if str(cid) in frozen:
            n_frozen += 1
            continue
        text = latest_prompt_text(Path(f"cases/pilot/case-{cid}"))
        w, h = bucket_for(text)
        for k in range(SEEDS_PER_PROMPT):
            seed = stable_seed(cid, args.round, k)
            tag = f"case{cid}-r{args.round}-s{seed}"
            if tag in done:
                continue
            lines.append(json.dumps({"prompt": text, "width": w, "height": h,
                                     "seed": seed, "type": tag}, ensure_ascii=False))
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"[gen-jsonl] round={args.round} pending={len(lines)} -> {out}")
    print(f"[gen-jsonl] frozen={n_frozen}")


if __name__ == "__main__":
    main()
