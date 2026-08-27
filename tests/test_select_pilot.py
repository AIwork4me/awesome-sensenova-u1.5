import json
import select_pilot as sp


def _mk(cid, cat, prompt):
    return {"id": cid, "title": f"t{cid}", "category": cat, "prompt": prompt,
            "image": f"/images/case{cid}.jpg", "sourceUrl": "https://x.com/x"}


def _bank():
    c = [_mk(i, "Posters & Typography", "poster art") for i in range(10)]
    c += [_mk(100 + i, "UI & Interfaces", "clean ui screenshot") for i in range(8)]
    c += [_mk(200, "Photography & Realism", "upload your portrait and edit it")]
    return {"repository": "r", "cases": c}


def test_edit_cases_filtered(tmp_path):
    picked = sp.pick_cases(_bank(), exclude_file=None)
    ids = [x["id"] for x in picked]
    assert 200 not in ids


def test_quota_total_and_order(tmp_path):
    picked = sp.pick_cases(_bank(), exclude_file=None)
    cats = {}
    for x in picked:
        cats[x["category"]] = cats.get(x["category"], 0) + 1
    assert sum(cats.values()) == min(sp.PILOT_SIZE, 18)  # bank too small → take all
    assert picked == sorted(picked, key=lambda x: x["id"])
