#!/usr/bin/env python3
"""Select the 30-case pilot batch deterministically (spec §5 SELECT)."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from lib.constants import PILOT_SIZE
from lib.ledger import append_event

QUOTAS = {
    "Posters & Typography": 6,
    "Photography & Realism": 4,
    "UI & Interfaces": 4,
    "Illustration & Art": 3,
    "Charts & Infographics": 2,
    "Products & E-commerce": 2,
    "Brand & Logos": 1,
    "Scenes & Storytelling": 2,
    "Architecture & Spaces": 1,
    "History & Classical Themes": 2,
    "Documents & Publishing": 1,
    "Characters & People": 1,
    "Other Use Cases": 1,
}
EDIT_MARKERS = (
    "upload", "uploads", "uploaded", "attach ", "attached",
    "photo i provide", "provide the photo", "for each photo",
    "reference image you", "the uploaded",
)


def is_edit_case(prompt: str) -> bool:
    low = " " + prompt.lower()
    return any(m in low for m in EDIT_MARKERS)


def pick_cases(cases_data: dict, exclude_file) -> list:
    """Filter, then quota-sample per category (id-ascending), redistributing any
    shortfall to still-hungry categories in quota-decreasing order."""
    excludes = set()
    if exclude_file and Path(exclude_file).exists():
        excludes = {int(x) for x in Path(exclude_file).read_text().split() if x.strip().isdigit()}
    by_cat = {}
    for c in cases_data["cases"]:
        if c["id"] in excludes or is_edit_case(c.get("prompt", "")):
            continue
        by_cat.setdefault(c.get("category", "Other Use Cases"), []).append(c)
    picked = []
    hungry = []
    for cat, quota in sorted(QUOTAS.items(), key=lambda kv: -kv[1]):
        cand = sorted(by_cat.get(cat, []), key=lambda x: x["id"])[:quota]
        picked += cand
        short = quota - len(cand)
        if short > 0 and by_cat.get(cat):
            hungry.append((short, cat))
    if hungry:
        taken_ids = {x["id"] for x in picked}
        for _, cat in hungry:
            rest = [x for x in sorted(by_cat.get(cat, []), key=lambda x: x["id"]) if x["id"] not in taken_ids]
            picked += rest[:1]
            taken_ids |= {x["id"] for x in rest[:1]}
    if len(picked) < PILOT_SIZE:
        # Bank too small to satisfy quotas: top up from every leftover case.
        taken_ids = {x["id"] for x in picked}
        leftovers = [x for cat in by_cat for x in by_cat[cat] if x["id"] not in taken_ids]
        picked += sorted(leftovers, key=lambda x: x["id"])[:PILOT_SIZE - len(picked)]
    return sorted(picked, key=lambda x: x["id"])[:PILOT_SIZE]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="third_party/ref/data/cases.json")
    ap.add_argument("--ledger", default="ledger/append.jsonl")
    ap.add_argument("--exclude-file", default="configs/exclude-cases.txt")
    args = ap.parse_args()
    data = json.loads(Path(args.ref).read_text(encoding="utf-8"))
    cases = pick_cases(data, args.exclude_file)
    print(f"[select] picked {len(cases)} cases")
    cas_dir = Path("cases/pilot")
    lock_cases = []
    for c in cases:
        d = cas_dir / f"case-{c['id']}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "base.md").write_text(c["prompt"] + "\n", encoding="utf-8")
        meta = {"case_id": c["id"], "title": c.get("title"), "category": c.get("category"),
                "source_url": c.get("sourceUrl"), "upstream_image": c.get("image"),
                "styles": c.get("styles"), "scenes": c.get("scenes"),
                "selected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        (d / "provenance.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        append_event(args.ledger, "case_selected", {"case_id": c["id"]}, idem=f"sel-{c['id']}")
        lock_cases.append({"id": c["id"], "title": c.get("title"), "category": c.get("category"),
                           "prompt_len": len(c.get("prompt", ""))})
    manifest = json.loads(Path("third_party/ref-manifest.json").read_text())
    Path("configs").mkdir(parents=True, exist_ok=True)
    Path("configs/pilot.lock.json").write_text(json.dumps(
        {"upstream_commit": manifest["commit"], "cases_sha256": manifest["cases_sha256"],
         "size": len(lock_cases), "cases": lock_cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    # Curation is not fully automatic by design: surface picks for a human glance.
    risky = [c["id"] for c in cases if c.get("category") in ("Characters & People", "Photography & Realism")]
    if risky:
        print(f"[review] likeness-sensitive categories picked: {risky}", file=sys.stderr)


if __name__ == "__main__":
    main()
