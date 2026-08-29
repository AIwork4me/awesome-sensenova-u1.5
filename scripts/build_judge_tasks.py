#!/usr/bin/env python3
"""Assemble a blinded judging queue for one round (spec §6.2, §6.4)."""
import argparse
import hashlib
import json
import random
import re
import shutil
from pathlib import Path

from lib.ledger import load_events
from make_gen_jsonl import latest_prompt_text

TAG_RE = re.compile(r"^case(\d+)-r(\d+)-s(\d+)$")


def neutral_entry_id(image_bytes: bytes) -> str:
    return "entry-" + hashlib.sha256(image_bytes).hexdigest()[:8]


def plan_rows(gen_events, case_dirs, baseline_existing, queue_dir: Path, rnd: int, copies=False,
              manifest_dir: Path | None = None):
    """Return shuffled row dicts; with copies=True also materialize the queue dir.

    With manifest_dir set (future --isolated runs) the provenance manifest is
    written outside the judge-visible queue dir; historical default keeps it in
    queue_dir so frozen artifacts and the operator workflow stay unchanged."""
    q = Path(queue_dir)
    rows = []
    for ev in gen_events:
        pay = ev["payload"]
        m = TAG_RE.match(pay["tag"])
        if m is None:
            raise KeyError(f"[FATAL] generated tag {pay['tag']!r} does not match "
                           f"{TAG_RE.pattern!r}; ledger and batch format are coupled, refusing to continue")
        case_id = int(m.group(1))
        cd = Path(f"cases/pilot/case-{case_id}")
        rows.append({"source": "sensenova", "case_id": case_id, "round": rnd,
                     "seed": pay["tag"].rsplit("-s", 1)[-1],
                     "orig_image": pay["file"],
                     "prompt_text": latest_prompt_text(cd)})
    for case_id, meta in sorted(case_dirs.items()):
        if case_id in baseline_existing:
            continue
        rows.append({"source": "reference", "case_id": case_id, "round": None,
                     "seed": None, "orig_image": str(meta["upstream_image"]),
                     "prompt_text": meta["prompt_text"]})
    rng = random.Random(int(hashlib.sha256(f"queue-{rnd}".encode()).hexdigest()[:16], 16))
    rng.shuffle(rows)
    made = []
    seen_ids = {}
    (q / "entries").mkdir(parents=True, exist_ok=True)
    (q / "prompts").mkdir(parents=True, exist_ok=True)
    (q / "verdicts").mkdir(parents=True, exist_ok=True)
    for row in rows:
        raw = Path(row["orig_image"]).read_bytes()
        eid = neutral_entry_id(raw)
        if eid in seen_ids:
            raise SystemExit(f"[FATAL] entry id collision {eid}: {seen_ids[eid]} vs {row['orig_image']}")
        seen_ids[eid] = row["orig_image"]
        ipath = q / "entries" / f"{eid}{Path(row['orig_image']).suffix.lower()}"
        ppath = q / "prompts" / f"{eid}.txt"
        vpath = q / "verdicts" / f"{eid}.json"
        if vpath.exists():
            continue
        if copies:
            if not ipath.exists():
                shutil.copyfile(row["orig_image"], ipath)
            ppath.write_text(row["prompt_text"], encoding="utf-8")
        made.append({"entry_id": eid, "source": row["source"], "case_id": row["case_id"],
                     "round": row["round"], "seed": row["seed"],
                     "image_path": str(ipath), "prompt_path": str(ppath),
                     "verdict_path": str(vpath), "prompt_text": row["prompt_text"]})
    if copies:
        manifest = [{"entry_id": r["entry_id"], "source": r["source"], "case_id": r["case_id"],
                     "round": r["round"], "seed": r["seed"],
                     "orig_image": r["image_path"],
                     "prompt_text_sha": hashlib.sha256(r["prompt_text"].encode()).hexdigest()}
                    for r in made]
        mdir = Path(manifest_dir) if manifest_dir is not None else q
        mdir.mkdir(parents=True, exist_ok=True)
        (mdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
        with (q / "tasks.jsonl").open("w", encoding="utf-8") as f:
            for r in made:
                f.write(json.dumps({k: r[k] for k in ("entry_id", "image_path", "prompt_path",
                                                      "verdict_path")}) + "\n")
    return [{k: v for k, v in r.items() if k != "prompt_text"} for r in made]


def main():
    ap = argparse.ArgumentParser(description="Assemble the blinded judging queue for one round.")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--isolated", action="store_true",
                    help="write the provenance manifest to runs/judge-private/round-N/ "
                         "instead of the judge-visible queue dir (source-isolated "
                         "judge workspace for future runs; historical frozen "
                         "artifacts are untouched)")
    args = ap.parse_args()
    gens = [e for e in load_events("ledger/append.jsonl") if e["type"] == "generated"]
    gens_r = [e for e in gens if f"-r{args.round}-" in e["payload"]["tag"]]
    lock = json.loads(Path("configs/pilot.lock.json").read_text(encoding="utf-8"))
    refs_root = Path("third_party/ref/data/images")
    # Only cases with generations this round get their upstream reference enqueued
    # (first time ever); the _baseline cache keeps them out of later rounds.
    round_cases = {int(m.group(1)) for e in gens_r
                   if (m := TAG_RE.match(e["payload"]["tag"]))}
    case_dirs = {}
    for c in lock["cases"]:
        if c["id"] not in round_cases:
            continue
        cd = Path(f"cases/pilot/case-{c['id']}")
        prov = json.loads((cd / "provenance.json").read_text(encoding="utf-8"))
        imgs = list(refs_root.glob(f"case{c['id']}.*"))
        if not imgs:
            raise SystemExit(f"[FATAL] upstream image missing for case {c['id']}")
        case_dirs[c["id"]] = {"prompt_text": (cd / "base.md").read_text(encoding="utf-8"),
                              "upstream_image": imgs[0], "prov": prov}
    baseline = {json.loads(p.read_text(encoding="utf-8"))["case_id"]
                for p in Path("results/judge/_baseline").glob("*.json")}
    rows = plan_rows(gens_r, case_dirs, baseline,
                     Path(f"runs/judge-queue/round-{args.round}"), args.round, copies=True,
                     manifest_dir=(Path(f"runs/judge-private/round-{args.round}")
                                   if args.isolated else None))
    print(f"[judge-queue] round={args.round} entries={len(rows)} "
          f"manifest={'runs/judge-private/round-' + str(args.round) if args.isolated else 'queue dir'}")


if __name__ == "__main__":
    main()
