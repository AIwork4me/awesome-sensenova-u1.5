import json
from pathlib import Path

from fixtures import GOOD_VERDICT
from lib.ledger import append_event
from schemas import SCORE_KEYS
import compare_parity as cp

S = lambda q: {k: q for k in SCORE_KEYS}


def _env(entry, src, case, rnd, q, flags, seed="1"):
    v = json.loads(json.dumps(GOOD_VERDICT))
    v["scores"] = S(q)
    # Brief-fixture gap fix: the brief's helper accepted `flags` but never
    # applied them, leaving every candidate with GOOD hard_flags; the four
    # boundary cases only test what they claim once flags are wired through.
    v["hard_flags"] = json.loads(json.dumps(flags))
    return {"schema_version": "1.0", "entry_id": entry, "backend": "agent", "judged_at": "t",
            "source": src, "case_id": case, "round": rnd, "seed": seed, "verdict": v}


def _layout(tmp_path, baseline_env, cand_env):
    (tmp_path / "results/judge/_baseline").mkdir(parents=True)
    (tmp_path / "results/judge").mkdir(parents=True, exist_ok=True)
    b = tmp_path / f"results/judge/_baseline/{cand_env['case_id']}.json"
    b.write_text(json.dumps(baseline_env))
    c = tmp_path / f"results/judge/{cand_env['entry_id']}.json"
    c.write_text(json.dumps(cand_env))
    (tmp_path / "runs/comparisons").mkdir(parents=True, exist_ok=True)
    return cand_env


def test_gap_exactly_at_allowance_passes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    e = _layout(tmp_path, _env("e0", "reference", 511, None, 8, GOOD_VERDICT["hard_flags"]),
                _env("e1", "sensenova", 511, 1, 8 - abs(cp.GAP_ALLOW), GOOD_VERDICT["hard_flags"]))
    row = cp.decide(e, _env("e0", "reference", 511, None, 8, GOOD_VERDICT["hard_flags"]), False)
    assert row["status"] == "parity"


def test_garbled_small_text_fails_without_exempt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bad = json.loads(json.dumps(GOOD_VERDICT["hard_flags"])) | {"small_text_quality": "garbled"}
    e = _env("e1", "sensenova", 511, 1, 10, bad)
    row = cp.decide(e, _env("e0", "reference", 511, None, 0, GOOD_VERDICT["hard_flags"]), False)
    assert row["status"] == "fail" and not row["checks"]["c_small_text"]
    assert row["failed_checks"] == ["c_small_text: garbled small text"]


def test_visual_defect_fails_even_with_high_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bad = json.loads(json.dumps(GOOD_VERDICT["hard_flags"])) | {"visual_defects": True}
    e = _env("e1", "sensenova", 511, 1, 10, bad)
    row = cp.decide(e, _env("e0", "reference", 511, None, 0, GOOD_VERDICT["hard_flags"]), False)
    assert row["status"] == "fail" and not row["checks"]["e_no_visual_defects"]
    assert any(x.startswith("e_no_visual_defects:") for x in row["failed_checks"])


def test_exempt_rescues_garbled_case(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bad = json.loads(json.dumps(GOOD_VERDICT["hard_flags"])) | {"small_text_quality": "garbled"}
    e = _env("e1", "sensenova", 511, 2, 9, bad)
    row = cp.decide(e, _env("e0", "reference", 511, None, 8, GOOD_VERDICT["hard_flags"]), True)
    # A rescued case stays "parity" even with a higher mean: the exemption is a
    # documented anomaly, not evidence the candidate beat the baseline outright.
    assert row["status"] == "parity" and row["checks"]["c_small_text"]


# --- end-to-end drill: main() over a synthetic repo layout -------------------


def _lock(tmp_path, ids):
    p = tmp_path / "configs/pilot.lock.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"size": len(ids),
                             "cases": [{"id": i, "title": f"c{i}"} for i in ids]}))


def _prov(tmp_path, case_id, exempt):
    p = tmp_path / f"cases/pilot/case-{case_id}/provenance.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"history": [{"small_text_exempt": exempt}]}))


def test_main_best_of_n_winner_report_and_freeze(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _lock(tmp_path, [11])
    _layout(tmp_path,
            _env("e-base", "reference", 11, None, 8, GOOD_VERDICT["hard_flags"]),
            _env("entry-worse", "sensenova", 11, 1, 6, GOOD_VERDICT["hard_flags"], seed="111"))
    best = _env("entry-best", "sensenova", 11, 1, 9, GOOD_VERDICT["hard_flags"], seed="222")
    (tmp_path / "results/judge/entry-best.json").write_text(json.dumps(best))
    append_event("ledger/append.jsonl", "generated",
                 {"tag": "case11-r1-s222", "file": "runs/genimages/round-1/keep.png"}, idem="case11-r1-s222")
    assert cp.main(["--round", "1"]) == 0
    rep = json.loads((tmp_path / "runs/comparisons/round-1/report.json").read_text())
    row = rep["per_case"][0]
    assert rep["round"] == 1 and rep["deferred"] == []
    assert row["case_id"] == 11 and row["status"] == "win"
    assert row["winner_entry_id"] == "entry-best" and row["winner_seed"] == "222"
    assert row["winner_file"] == "runs/genimages/round-1/keep.png"
    assert all(row["checks"].values()) and row["failed_checks"] == []
    m = rep["milestone"]
    assert (m["parity_count"], m["win_count"], m["target"], m["total"]) == (0, 1, 24, 1)
    assert m["parity_ratio"] == 1.0 and m["overall_gap"] == 1.0
    lines = Path("ledger/append.jsonl").read_text().splitlines()
    types = sorted((json.loads(l)["type"], json.loads(l)["idem"]) for l in lines
                   if json.loads(l)["type"] in ("compared", "status_parity"))
    assert types == [("compared", "cmp-1-11"), ("status_parity", "cmp-1-11")]
    # rerun must be idempotent through the ledger dedupe
    n = len(Path("ledger/append.jsonl").read_text().splitlines())
    assert cp.main(["--round", "1"]) == 0
    assert len(Path("ledger/append.jsonl").read_text().splitlines()) == n


def test_main_partial_round_defers_and_exempts_via_provenance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _lock(tmp_path, [11, 22, 33])
    bad = dict(GOOD_VERDICT["hard_flags"], small_text_quality="garbled")
    _layout(tmp_path,
            _env("e-b11", "reference", 11, None, 8, GOOD_VERDICT["hard_flags"]),
            _env("e-c11", "sensenova", 11, 1, 8, GOOD_VERDICT["hard_flags"]))          # parity
    base22 = tmp_path / "results/judge/_baseline/22.json"
    base22.write_text(json.dumps(_env("e-b22", "reference", 22, None, 8, GOOD_VERDICT["hard_flags"])))
    (tmp_path / "results/judge/_baseline/33.json").write_text(
        json.dumps(_env("e-b33", "reference", 33, None, 8, GOOD_VERDICT["hard_flags"])))
    (tmp_path / "results/judge/e-c33.json").write_text(
        json.dumps(_env("e-c33", "sensenova", 33, 1, 8, bad)))                          # garbled
    _prov(tmp_path, 33, exempt=True)                                                    # rescued -> parity
    assert cp.main(["--round", "1"]) == 0
    rep = json.loads((tmp_path / "runs/comparisons/round-1/report.json").read_text())
    by_id = {r["case_id"]: r for r in rep["per_case"]}
    assert rep["deferred"] == [22]                       # candidate never judged this round
    assert by_id[11]["status"] == "parity"
    assert by_id[33]["status"] == "parity" and by_id[33]["checks"]["c_small_text"]
    m = rep["milestone"]
    assert m["total"] == 2 and m["parity_count"] == 2    # deferred excluded from denominator
    assert m["parity_ratio"] == 1.0
    idems = {json.loads(l)["idem"] for l in Path("ledger/append.jsonl").read_text().splitlines()}
    assert idems == {"cmp-1-11", "cmp-1-33"}             # no events for deferred case


def test_round2_report_carries_frozen_rows_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _lock(tmp_path, [11, 22])
    flags = GOOD_VERDICT["hard_flags"]
    # Round 1: case 11 decided (win); case 22 deferred (baseline present,
    # candidate never judged).
    _layout(tmp_path,
            _env("e-b11", "reference", 11, None, 8, flags),
            _env("e-c11", "sensenova", 11, 1, 9, flags, seed="111"))
    (tmp_path / "results/judge/_baseline/22.json").write_text(
        json.dumps(_env("e-b22", "reference", 22, None, 8, flags)))
    assert cp.main(["--round", "1"]) == 0
    rep1 = json.loads((tmp_path / "runs/comparisons/round-1/report.json").read_text())
    assert [r["case_id"] for r in rep1["per_case"]] == [11] and rep1["deferred"] == [22]
    # Round 2: only case 22 is decided; frozen case 11 generates nothing and
    # must reappear via carried_from_round so the report stays cumulative.
    (tmp_path / "results/judge/e-c22r2.json").write_text(
        json.dumps(_env("e-c22r2", "sensenova", 22, 2, 8, flags)))
    assert cp.main(["--round", "2"]) == 0
    rep2 = json.loads((tmp_path / "runs/comparisons/round-2/report.json").read_text())
    by_id = {r["case_id"]: r for r in rep2["per_case"]}
    assert set(by_id) == {11, 22}
    assert by_id[11]["carried_from_round"] == 1          # frozen row stays visible
    assert by_id[11]["status"] == "win"
    assert "carried_from_round" not in by_id[22]         # fresh rows stay fresh
    assert by_id[22]["status"] == "parity"
    m = rep2["milestone"]
    assert m["total"] == 2 and (m["win_count"], m["parity_count"]) == (1, 1)
    assert m["parity_ratio"] == 1.0                      # carried counts like fresh
    assert rep2["deferred"] == []
    # Idempotent rerun of round 2: no duplicate carried rows, no new ledger events.
    n_events = len(Path("ledger/append.jsonl").read_text().splitlines())
    assert cp.main(["--round", "2"]) == 0
    rep2b = json.loads((tmp_path / "runs/comparisons/round-2/report.json").read_text())
    assert len(rep2b["per_case"]) == 2
    assert sum(1 for r in rep2b["per_case"] if r.get("carried_from_round") == 1) == 1
    assert len(Path("ledger/append.jsonl").read_text().splitlines()) == n_events
