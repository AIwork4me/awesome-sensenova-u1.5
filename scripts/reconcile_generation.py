#!/usr/bin/env python3
"""Map produced images back to tags and record generated/gen_failed events."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from lib.ledger import append_event, load_events

NAME_RE = re.compile(r"^(\d{4})_(.+)-r(\d+)-s(\d+)_(\d+)x(\d+)\.png$")
# NOTE: the `type` field we emit is `case{id}-r{n}-s{seed}`, so group(2) here is
# `case{id}` and groups 3/4 carry round/seed again. The full tag is group(2)+suffix.


def parse_tags(img_dir: Path) -> dict:
    out = {}
    for f in sorted(Path(img_dir).iterdir()):
        m = NAME_RE.match(f.name)
        if not m:
            continue
        tag = f"{m.group(2)}-r{m.group(3)}-s{m.group(4)}"
        out[tag] = f.name
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--ledger", default="ledger/append.jsonl")
    args = ap.parse_args()
    img_dir = Path(f"runs/genimages/round-{args.round}")
    want = {}
    for line in Path(f"runs/gen/round-{args.round}/gen.jsonl").read_text().splitlines():
        if line.strip():
            s = json.loads(line)
            want[s["type"]] = s
    have = parse_tags(img_dir)
    have_all = {ev["payload"]["tag"] for ev in load_events(args.ledger) if ev["type"] == "generated"}
    for tag in sorted(want):
        if tag in have_all:
            continue
        fn = have.get(tag)
        if not fn:
            append_event(args.ledger, "gen_failed",
                         {"tag": tag, "attempt": args.attempt}, idem=f"{tag}#{args.attempt}")
            continue
        p = img_dir / fn
        append_event(args.ledger, "generated",
                     {"tag": tag, "file": str(p),
                      "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}, idem=tag)
    print(f"[reconcile] want={len(want)} new_done={sum(1 for t in want if t in have and t not in have_all)}")


if __name__ == "__main__":
    main()
